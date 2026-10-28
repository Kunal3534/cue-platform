"""Auth helpers for v1.

Two modes:
  DEV  — DEV_AUTO_LOGIN_EMAIL is set → every request returns that user (no cookie).
  PROD — `cue_session` signed cookie (itsdangerous) contains the user-id.
         Magic-link flow (routes/auth.py) issues the cookie.

`current_user` is a FastAPI dependency used by all v1 routes.
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_async_db
from .models import User


async def may_sign_in(email: str, session) -> bool:
    """Who gets through the door: the env allowlist (producers), anyone a
    producer has added as a workspace member, or everyone when the allowlist
    is empty (dev)."""
    import sqlalchemy as sa
    allowed = {e.strip().lower() for e in settings.allowed_emails.split(",") if e.strip()}
    if not allowed or email.lower() in allowed:
        return True
    row = (await session.execute(
        sa.text("SELECT 1 FROM workspace_members WHERE email = :em LIMIT 1"),
        {"em": email.lower()},
    )).first()
    return bool(row)


def is_team_member(user: User) -> bool:
    """Allowlisted producers act as one team: every listed email can see and
    edit every project on this instance. With an empty allowlist (dev), only
    ownership grants access."""
    allowed = {e.strip().lower() for e in settings.allowed_emails.split(",") if e.strip()}
    return user.email.lower() in allowed


# ---------------------------------------------------------------------------
# Session cookie helpers
# ---------------------------------------------------------------------------

_COOKIE_NAME = "cue_session"
_SALT = "cue-session-v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SALT)


def make_session_cookie(user_id: str) -> str:
    """Return a signed value to set as the cue_session cookie."""
    return _serializer().dumps(user_id)


def decode_session_cookie(value: str, max_age_seconds: int = 86400 * 30) -> str:
    """Return user_id or raise HTTPException(401)."""
    try:
        return _serializer().loads(value, max_age=max_age_seconds)
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session")


# ---------------------------------------------------------------------------
# current_user dependency
# ---------------------------------------------------------------------------

async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_async_db),
) -> User:
    # ── Dev bypass ──────────────────────────────────────────────────────────
    if settings.dev_auto_login_email:
        email = settings.dev_auto_login_email
        row = (await session.execute(
            sa.select(User).where(User.email == email)
        )).scalar_one_or_none()
        if row is None:
            row = User(id=str(uuid.uuid4()), email=email, name=email.split("@")[0])
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    # ── Production: read signed cookie ──────────────────────────────────────
    cookie = request.cookies.get(_COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not signed in")

    user_id = decode_session_cookie(cookie)
    row = (await session.execute(
        sa.select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="User not found")
    return row
