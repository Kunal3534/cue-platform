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

    # Closed instance: producers (env allowlist) + added workspace members
    from ..auth import may_sign_in
    if not await may_sign_in(email, session):
        raise HTTPException(status_code=403, detail="This email is not authorised to sign in")

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

    base_url = (settings.public_api_url or str(request.base_url)).rstrip("/")
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
# Google OAuth — "Continue with Google" + offline Calendar access
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_SCOPES = ("openid email profile "
                  "https://www.googleapis.com/auth/calendar.events "
                  # drive.file = only files the app creates or the user picks
                  "https://www.googleapis.com/auth/drive.file")


def _google_redirect_uri(request: Request) -> str:
    base = (settings.public_api_url or str(request.base_url)).rstrip("/")
    return f"{base}/auth/google/callback"


def _state_token() -> str:
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(settings.secret_key, salt="google-oauth-state")
    return s.dumps({"n": str(uuid.uuid4())})


def _check_state(state: str) -> None:
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    s = URLSafeTimedSerializer(settings.secret_key, salt="google-oauth-state")
    try:
        s.loads(state, max_age=600)
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid sign-in state — try again")


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503,
                            detail="Google sign-in is not configured (GOOGLE_CLIENT_ID/SECRET)")
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": _google_redirect_uri(request),
        "response_type": "code",
        "scope": _GOOGLE_SCOPES,
        # offline + consent → Google returns a refresh token we can keep
        # using to write shoot events into the user's Calendar
        "access_type": "offline",
        "prompt": "consent",
        "state": _state_token(),
    })
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{params}", status_code=302)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_async_db),
) -> RedirectResponse:
    if error or not code or not state:
        return RedirectResponse(
            url=f"{settings.frontend_origin}/login?error=google", status_code=302)
    _check_state(state)

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": _google_redirect_uri(request),
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google token exchange failed")
        tokens = token_resp.json()
        info_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if info_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not read the Google profile")
        info = info_resp.json()

    email = (info.get("email") or "").lower().strip()
    if not email or not info.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google account has no verified email")

    # Same closed-instance rule as magic links
    from ..auth import may_sign_in
    if not await may_sign_in(email, session):
        return RedirectResponse(
            url=f"{settings.frontend_origin}/login?error=not-allowed", status_code=302)

    user = await _get_or_create_user(email, session)
    display_name = info.get("name") or user.name
    refresh = tokens.get("refresh_token")  # present because prompt=consent
    await session.execute(
        sa.text("UPDATE users SET name = :nm, google_sub = :sub, "
                "google_refresh_token = COALESCE(:rt, google_refresh_token), "
                "google_calendar_connected = (COALESCE(:rt, google_refresh_token) IS NOT NULL) "
                "WHERE id = :id"),
        {"nm": display_name, "sub": info.get("sub"), "rt": refresh, "id": user.id},
    )
    await session.commit()

    response = RedirectResponse(url=settings.frontend_origin, status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=make_session_cookie(user.id),
        httponly=True,
        samesite="lax",
        secure=not bool(settings.dev_auto_login_email),
        max_age=_COOKIE_MAX_AGE,
    )
    return response


@router.get("/google/picker")
async def google_picker_config(
    user: User = Depends(current_user),
) -> dict:
    """Short-lived config for the Google Picker dialog: the browser needs an
    access token for the signed-in user's grant plus the public API key."""
    if not user.google_refresh_token:
        raise HTTPException(status_code=409, detail="Connect Google first")
    if not settings.google_api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY is not configured")
    from ..services.google_calendar import access_token_for
    token = await access_token_for(user.google_refresh_token)
    if not token:
        raise HTTPException(status_code=409, detail="Google access expired — reconnect Google")
    return {"access_token": token, "api_key": settings.google_api_key}


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
    google_calendar_connected: bool = False
    created_at: str


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(current_user)) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        google_calendar_connected=bool(user.google_calendar_connected),
        created_at=user.created_at.isoformat(),
    )
