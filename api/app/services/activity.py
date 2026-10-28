"""Activity log — who changed what, when.

Two producers (plus Kunal) edit the same board, so every mutation records a
human-readable line. Inserted inside the caller's transaction: the caller
commits, so a failed mutation never logs.
"""
from __future__ import annotations

import json
import uuid
from datetime import date as date_cls

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


def fmt_day(d: date_cls | str) -> str:
    """'2026-11-11' → '11 Nov' — how days are referred to in log lines."""
    if isinstance(d, str):
        d = date_cls.fromisoformat(d)
    return f"{d.day} {d.strftime('%b')}"


async def log(
    session: AsyncSession,
    project_id: str,
    user: User | None,
    action: str,
    summary: str,
    detail: dict | None = None,
) -> None:
    await session.execute(
        sa.text(
            "INSERT INTO activity_log (id, project_id, user_email, action, summary, detail, created_at) "
            "VALUES (:id, :pid, :em, :ac, :su, CAST(:de AS jsonb), NOW())"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": project_id,
            "em": user.email if user else None,
            "ac": action,
            "su": summary,
            "de": json.dumps(detail) if detail else None,
        },
    )
