"""FlagDetector — runs all rules against a ProjectGraph and writes results to
the flags table.

New flags are inserted; flags whose title+kind no longer fire are resolved
(resolved_at set).  SSE events are published for both new and resolved flags.

Usage (from worker):
    await FlagDetector.run(project_id, scenario_id, session)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .project_graph import ProjectGraph
from .flag_rules import (
    cast_holds,
    permit_leads,
    weather_conflicts,
    drone_nofly,
    cost_overruns,
    missing_data,
    continuity,
)
from . import sse as _sse

_RULES = [
    cast_holds,
    permit_leads,
    weather_conflicts,
    drone_nofly,
    cost_overruns,
    missing_data,
    continuity,
]


class FlagDetector:

    @staticmethod
    async def run(
        project_id: str,
        scenario_id: str | None,
        session: AsyncSession,
    ) -> dict[str, int]:
        """Run all rules; upsert flags; publish SSE events.

        Returns {"raised": N, "resolved": N}.
        """
        pg = await ProjectGraph.load(project_id, scenario_id, session)

        # Collect all rule results
        fresh_flags: list[dict[str, Any]] = []
        for rule_module in _RULES:
            try:
                fresh_flags.extend(rule_module.detect(pg))
            except Exception as exc:
                # A broken rule must not block the detector
                fresh_flags.append({
                    "kind": "custom",
                    "severity": "info",
                    "title": f"Flag rule error: {rule_module.__name__}",
                    "description": str(exc),
                })

        # Load currently open flags for this project
        existing_rows = (await session.execute(
            sa.text(
                "SELECT id, kind, title FROM flags "
                "WHERE project_id=:pid AND resolved_at IS NULL AND dismissed=FALSE"
            ),
            {"pid": project_id},
        )).fetchall()
        existing_keys = {(r.kind, r.title): r.id for r in existing_rows}

        raised = 0
        for flag in fresh_flags:
            key = (flag["kind"], flag["title"])
            if key in existing_keys:
                continue  # already open — don't duplicate
            flag_id = str(uuid.uuid4())
            await session.execute(
                sa.text(
                    "INSERT INTO flags "
                    "(id, project_id, kind, severity, title, description, "
                    " raised_at, raised_by, related_day_id, related_character_id) "
                    "VALUES (:id, :pid, :kind, :sev, :title, :desc, "
                    "        NOW(), 'system', :day_id, :char_id)"
                ),
                {
                    "id": flag_id,
                    "pid": project_id,
                    "kind": flag["kind"],
                    "sev": flag["severity"],
                    "title": flag["title"],
                    "desc": flag.get("description"),
                    "day_id": flag.get("related_day_id"),
                    "char_id": flag.get("related_character_id"),
                },
            )
            raised += 1
            await _sse.publish(project_id, {
                "kind": "flag_raised",
                "flag_id": flag_id,
                "flag_kind": flag["kind"],
                "severity": flag["severity"],
                "title": flag["title"],
            })

        # Resolve flags whose condition no longer fires
        fresh_keys = {(f["kind"], f["title"]) for f in fresh_flags}
        resolved = 0
        for (kind, title), flag_id in existing_keys.items():
            if (kind, title) not in fresh_keys:
                await session.execute(
                    sa.text("UPDATE flags SET resolved_at=NOW() WHERE id=:id"),
                    {"id": flag_id},
                )
                resolved += 1
                await _sse.publish(project_id, {
                    "kind": "flag_resolved",
                    "flag_id": flag_id,
                })

        await session.commit()
        return {"raised": raised, "resolved": resolved}
