"""Magic-link auth routes.

POST /auth/request_link  — body: {email}; generates signed token, stores in
                           magic_links, sends email via Resend API.
GET  /auth/verify        — ?token=...; validates + consumes link, sets
                           cue_session cookie, redirects to frontend.
POST /auth/signout       — clears the session cookie.
GET  /auth/me            — returns the current user's profile.

Dev mode (DEV_AUTO_LOGIN_EMAIL set): request_link is a no-op that echoes the
magic link in the response body instead of emailing it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, make_session_cookie
from ..config import settings
from ..db import get_async_db
from ..models import MagicLink, User

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "cue_session"
_COOKIE_MAX_AGE = 86400 * 30  # 30 days


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(email: str) -> str:
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(settings.secret_key, salt="magic-link-v1")
    return s.dumps(email)


def _decode_token(token: str) -> str:
    """Return email or raise HTTPException(400)."""
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
    s = URLSafeTimedSerializer(settings.secret_key, salt="magic-link-v1")
    try:
        return s.loads(token, max_age=settings.magic_link_ttl_seconds)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Magic link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid magic link")


async def _get_or_create_user(email: str, session: AsyncSession) -> User:
    row = (await session.execute(
        sa.select(User).where(User.email == email)
    )).scalar_one_or_none()
    if row is None:
        row = User(id=str(uuid.uuid4()), email=email, name=email.split("@")[0])
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def _send_magic_link_email(email: str, link: str) -> None:
    """POST to Resend API. Silently skips if no API key configured."""
    if not settings.resend_api_key:
        return
    mail_from = settings.mail_from or "noreply@cue.app"
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": mail_from,
                "to": [email],
                "subject": "Sign in to Cue",
                "html": (
                    f"<p>Click the link below to sign in to Cue. "
                    f"It expires in {settings.magic_link_ttl_seconds // 60} minutes.</p>"
                    f'<p><a href="{link}">Sign in to Cue</a></p>'
                    f"<p style='color:#888;font-size:12px;'>{link}</p>"
                ),
            },
            timeout=10.0,
        )


# ---------------------------------------------------------------------------
# POST /auth/request_link
# ---------------------------------------------------------------------------

class RequestLinkBody(BaseModel):
    email: str  # EmailStr requires email-validator; keep plain str for now


@router.post("/request_link")
async def request_link(
    body: RequestLinkBody,
    request: Request,
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    email = body.email.lower().strip()
    token = _make_token(email)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.magic_link_ttl_seconds)

    # Store in magic_links (one per email at a time is fine for v1)
    await session.execute(
        sa.text("DELETE FROM magic_links WHERE email=:email"),
        {"email": email},
    )
    ml = MagicLink(
        id=str(uuid.uuid4()),
        email=email,
        token=token,
        expires_at=expires_at,
    )
    session.add(ml)
    await session.commit()

    base_url = str(request.base_url).rstrip("/")
    link = f"{base_url}/auth/verify?token={token}"

    # Dev mode: return the link in the response instead of emailing
    if settings.dev_auto_login_email:
        return {"ok": True, "dev_link": link}

    await _send_magic_link_email(email, link)
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /auth/verify
# ---------------------------------------------------------------------------

@router.get("/verify")
async def verify(
    token: str,
    session: AsyncSession = Depends(get_async_db),
) -> RedirectResponse:
    email = _decode_token(token)

    # Check magic_links table
    ml = (await session.execute(
        sa.select(MagicLink).where(
            MagicLink.token == token,
            MagicLink.consumed_at == None,  # noqa: E711
        )
    )).scalar_one_or_none()
    if not ml:
        raise HTTPException(status_code=400, detail="Magic link already used or not found")

    # Consume it
    await session.execute(
        sa.text("UPDATE magic_links SET consumed_at=NOW() WHERE id=:id"),
        {"id": ml.id},
    )

    user = await _get_or_create_user(email, session)
    cookie_value = make_session_cookie(user.id)

    # Redirect to frontend with cookie set
    response = RedirectResponse(url=settings.frontend_origin, status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        samesite="lax",
        secure=not bool(settings.dev_auto_login_email),  # secure only in prod
        max_age=_COOKIE_MAX_AGE,
    )
    return response


# ---------------------------------------------------------------------------
# POST /auth/signout
# ---------------------------------------------------------------------------

@router.post("/signout")
async def signout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(_COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    id: str
    email: str
    name: str | None
    created_at: str


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(current_user)) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at.isoformat(),
    )
