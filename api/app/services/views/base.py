"""Shared view-cache helpers used by all view renderers."""
from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def get_cached(
    project_id: str,
    view_name: str,
    scenario_id: str | None,
    session: AsyncSession,
) -> dict | None:
    row = (await session.execute(
        sa.text(
            "SELECT payload FROM view_cache "
            "WHERE project_id = :pid AND view_name = :name "
            "AND (scenario_id = :sid OR (:sid IS NULL AND scenario_id IS NULL))"
        ),
        {"pid": project_id, "name": view_name, "sid": scenario_id},
    )).first()
    return row.payload if row else None


async def save_cache(
    project_id: str,
    view_name: str,
    scenario_id: str | None,
    payload: dict,
    session: AsyncSession,
) -> None:
    await session.execute(
        sa.text(
            "DELETE FROM view_cache "
            "WHERE project_id = :pid AND view_name = :name "
            "AND (scenario_id = :sid OR (:sid IS NULL AND scenario_id IS NULL))"
        ),
        {"pid": project_id, "name": view_name, "sid": scenario_id},
    )
    await session.execute(
        sa.text(
            "INSERT INTO view_cache (id, project_id, view_name, scenario_id, payload, computed_at) "
            "VALUES (:id, :pid, :name, :sid, CAST(:payload AS JSONB), NOW())"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": project_id,
            "name": view_name,
            "sid": scenario_id,
            "payload": json.dumps(payload, default=str),
        },
    )


async def invalidate_views(
    project_id: str,
    view_names: list[str],
    scenario_id: str | None,
    session: AsyncSession,
) -> None:
    for view_name in view_names:
        await session.execute(
            sa.text(
                "DELETE FROM view_cache "
                "WHERE project_id = :pid AND view_name = :name "
                "AND (scenario_id = :sid OR (:sid IS NULL AND scenario_id IS NULL))"
            ),
            {"pid": project_id, "name": view_name, "sid": scenario_id},
        )
