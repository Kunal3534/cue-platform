"""Chat agent tool definitions and executor.

TOOLS       — list of Anthropic-format tool dicts passed to the messages API.
ToolExecutor — async class that runs each tool against the live DB and ProjectGraph.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .project_graph import ProjectGraph, fmt_pages
from .propagation_engine import PropagationEngine
from . import edit_applicator

# ---------------------------------------------------------------------------
# Tool schema definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_project_overview",
        "description": (
            "Return a concise summary of the project: title, window, total shoot days, "
            "principals cast, count of open flags, and what is scheduled tomorrow."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_day",
        "description": (
            "Return full detail of one shoot day — scenes, cast, camera units, "
            "JR count, location, shift, and any notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Shoot day number (e.g. '3') or ISO date (e.g. '2026-04-12').",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "find_scenes",
        "description": "Search scenes by cast, location, text, or D/N.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search against scene title and description.",
                },
                "filters": {
                    "type": "object",
                    "description": "Optional structured filters.",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "Canonical character name (case-insensitive).",
                        },
                        "location_name": {
                            "type": "string",
                            "description": "Partial location name match.",
                        },
                        "has_vfx": {"type": "boolean"},
                        "dn": {
                            "type": "string",
                            "enum": ["day", "night", "day_int", "night_int", "dusk"],
                        },
                    },
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_character_availability",
        "description": (
            "For one character, return W / H / · status across all shoot days "
            "and the total working-day count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "character": {
                    "type": "string",
                    "description": "Display name or canonical name (case-insensitive).",
                },
            },
            "required": ["character"],
        },
    },
    {
        "name": "propose_reschedule",
        "description": (
            "Simulate moving a scene from its current day to a different day. "
            "Returns a propagation preview with the diff. Does NOT commit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_number": {
                    "type": "string",
                    "description": "Scene number, e.g. '14' or '18A'.",
                },
                "to_day_identifier": {
                    "type": "string",
                    "description": "Destination shoot day number or ISO date.",
                },
            },
            "required": ["scene_number", "to_day_identifier"],
        },
    },
    {
        "name": "propose_swap_days",
        "description": (
            "Simulate swapping the complete scene content of two shoot days. "
            "Returns a propagation preview. Does NOT commit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day_a": {
                    "type": "string",
                    "description": "First shoot day number or ISO date.",
                },
                "day_b": {
                    "type": "string",
                    "description": "Second shoot day number or ISO date.",
                },
            },
            "required": ["day_a", "day_b"],
        },
    },
    {
        "name": "get_flags",
        "description": "List open (unresolved) flags for this project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "blocker"],
                    "description": "Filter to a specific severity level; omit to see all.",
                },
            },
        },
    },
    {
        "name": "commit_preview",
        "description": (
            "Commit a previously-proposed preview batch to the database. "
            "ONLY call this AFTER the user has given explicit confirmation. "
            "Never call speculatively."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "batch_id": {
                    "type": "string",
                    "description": "The batch_id returned by a propose_* tool.",
                },
            },
            "required": ["batch_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

class ToolExecutor:
    def __init__(
        self,
        project_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> None:
        self.project_id = project_id
        self.user_id = user_id
        self.session = session
        self._pg: ProjectGraph | None = None

    async def _graph(self) -> ProjectGraph:
        if self._pg is None:
            self._pg = await ProjectGraph.load(self.project_id, None, self.session)
        return self._pg

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch tool call by name; returns a JSON-serialisable result."""
        dispatch = {
            "get_project_overview":      self._get_project_overview,
            "get_day":                   self._get_day,
            "find_scenes":               self._find_scenes,
            "get_character_availability": self._get_character_availability,
            "propose_reschedule":        self._propose_reschedule,
            "propose_swap_days":         self._propose_swap_days,
            "get_flags":                 self._get_flags,
            "commit_preview":            self._commit_preview,
        }
        fn = dispatch.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return await fn(**arguments)
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------

    async def _get_project_overview(self) -> dict:
        pg = await self._graph()
        p = pg.project
        tomorrow = date.today()
        tomorrow_day = next(
            (d for d in pg.shoot_days if d.date > tomorrow),
            None,
        )
        flags_count = (await self.session.execute(
            sa.text(
                "SELECT COUNT(*) FROM flags "
                "WHERE project_id=:pid AND resolved_at IS NULL AND dismissed=FALSE"
            ),
            {"pid": self.project_id},
        )).scalar() or 0

        return {
            "title": p.title,
            "window": p.window,
            "status": p.status,
            "shoot_days_total": len(pg.shoot_days),
            "total_days": len(pg.days),
            "principals": [c.display_name for c in pg.characters if c.is_principal],
            "open_flags": int(flags_count),
            "next_shoot_day": (
                {
                    "shoot_day_number": tomorrow_day.shoot_day_number,
                    "date": tomorrow_day.date.isoformat(),
                    "location": tomorrow_day.location_name,
                    "scene_count": len(tomorrow_day.scenes),
                }
                if tomorrow_day
                else None
            ),
        }

    async def _get_day(self, identifier: str) -> dict:
        pg = await self._graph()
        day = None
        # Try as integer shoot day number
        try:
            sdn = int(identifier)
            day = next((d for d in pg.shoot_days if d.shoot_day_number == sdn), None)
        except ValueError:
            pass
        # Try as ISO date
        if day is None:
            try:
                target = date.fromisoformat(identifier)
                day = next((d for d in pg.days if d.date == target), None)
            except ValueError:
                pass
        if day is None:
            return {"error": f"Day not found: {identifier!r}"}

        return {
            "id": day.id,
            "date": day.date.isoformat(),
            "shoot_day_number": day.shoot_day_number,
            "kind": day.kind,
            "location": day.location_name,
            "location_area": day.location_area,
            "shift": (
                f"{day.shift_start.strftime('%H:%M')} — {day.shift_end.strftime('%H:%M')}"
                if day.shift_start and day.shift_end
                else None
            ),
            "jr_count": day.jr_count,
            "camera_units": [code for code, _k, _c in day.camera_uses],
            "scenes": [
                {
                    "scene_number": sc.scene_number,
                    "title": sc.title,
                    "dn": sc.dn,
                    "pages": fmt_pages(sc.page_eighths),
                    "characters": sc.characters,
                }
                for sc in day.scenes
            ],
            "cast": day.cast,
            "notes": day.notes,
            "banner_text": day.banner_text,
        }

    async def _find_scenes(self, query: str, filters: dict | None = None) -> dict:
        pg = await self._graph()
        filters = filters or {}
        query_lower = query.lower()

        results = []
        for day in pg.days:
            for sc in day.scenes:
                # Text match
                searchable = " ".join(filter(None, [sc.title, sc.description, sc.scene_number]))
                if query_lower and query_lower not in searchable.lower():
                    continue
                # Character filter
                if "character" in filters:
                    char_lower = filters["character"].lower()
                    if not any(char_lower in c.lower() for c in sc.characters):
                        continue
                # Location filter
                if "location_name" in filters:
                    loc = (sc.location_name or day.location_name or "").lower()
                    if filters["location_name"].lower() not in loc:
                        continue
                # D/N filter
                if "dn" in filters and sc.dn != filters["dn"]:
                    continue
                results.append({
                    "scene_number": sc.scene_number,
                    "title": sc.title,
                    "dn": sc.dn,
                    "pages": fmt_pages(sc.page_eighths),
                    "characters": sc.characters,
                    "location": sc.location_name or day.location_name,
                    "shoot_day": day.shoot_day_number,
                    "date": day.date.isoformat() if day.kind == "shoot" else None,
                })
        return {"count": len(results), "scenes": results[:50]}

    async def _get_character_availability(self, character: str) -> dict:
        pg = await self._graph()
        char_lower = character.lower()
        char = next(
            (
                c for c in pg.characters
                if c.canonical_name.lower() == char_lower
                or c.display_name.lower() == char_lower
            ),
            None,
        )
        if char is None:
            return {"error": f"Character not found: {character!r}"}

        dood = pg.character_dood.get(char.id, {})
        w = sum(1 for v in dood.values() if v == "W")
        h = sum(1 for v in dood.values() if v == "H")
        return {
            "character": char.display_name,
            "actor": char.actor_name,
            "is_principal": char.is_principal,
            "dood": {str(k): v for k, v in sorted(dood.items())},
            "summary": {"W": w, "H": h, "T": w + h},
        }

    def _resolve_day_id(self, pg: ProjectGraph, identifier: str) -> str | None:
        try:
            sdn = int(identifier)
            d = next((x for x in pg.shoot_days if x.shoot_day_number == sdn), None)
            return d.id if d else None
        except ValueError:
            pass
        try:
            target = date.fromisoformat(identifier)
            d = next((x for x in pg.days if x.date == target), None)
            return d.id if d else None
        except ValueError:
            return None

    async def _propose_reschedule(self, scene_number: str, to_day_identifier: str) -> dict:
        pg = await self._graph()
        # Find scene
        sc = None
        for day in pg.days:
            for s in day.scenes:
                if s.scene_number == scene_number:
                    sc = s
                    break

        if sc is None:
            return {"error": f"Scene {scene_number!r} not found"}

        to_day_id = self._resolve_day_id(pg, to_day_identifier)
        if to_day_id is None:
            return {"error": f"Day not found: {to_day_identifier!r}"}

        # Find current day_scene link
        ds_row = (await self.session.execute(
            sa.text("SELECT id FROM day_scenes WHERE scene_id = :sid"),
            {"sid": sc.id},
        )).first()
        if not ds_row:
            return {"error": f"Scene {scene_number} is not currently scheduled on any day"}

        raw_edits = [
            {
                "op": "patch",
                "entity": "day_scenes",
                "id": ds_row.id,
                "fields": {"day_id": to_day_id, "order_in_day": 999},
            }
        ]
        preview = await PropagationEngine.preview(
            project_id=self.project_id,
            user_id=self.user_id,
            raw_edits=raw_edits,
            session=self.session,
        )
        self._pg = None  # invalidate cached graph
        diff = dict(preview.diff or {})
        diff.pop("request", None)
        return {
            "batch_id": preview.batch_id,
            "expires_at": preview.expires_at.isoformat(),
            "diff": diff,
        }

    async def _propose_swap_days(self, day_a: str, day_b: str) -> dict:
        pg = await self._graph()
        id_a = self._resolve_day_id(pg, day_a)
        id_b = self._resolve_day_id(pg, day_b)
        if id_a is None:
            return {"error": f"Day not found: {day_a!r}"}
        if id_b is None:
            return {"error": f"Day not found: {day_b!r}"}

        day_obj_a = next(d for d in pg.days if d.id == id_a)
        day_obj_b = next(d for d in pg.days if d.id == id_b)

        raw_edits: list[dict] = []
        # Move all scenes from A → B
        for sc in day_obj_a.scenes:
            ds_row = (await self.session.execute(
                sa.text("SELECT id FROM day_scenes WHERE scene_id = :sid AND day_id = :did"),
                {"sid": sc.id, "did": id_a},
            )).first()
            if ds_row:
                raw_edits.append({
                    "op": "patch", "entity": "day_scenes", "id": ds_row.id,
                    "fields": {"day_id": id_b},
                })
        # Move all scenes from B → A
        for sc in day_obj_b.scenes:
            ds_row = (await self.session.execute(
                sa.text("SELECT id FROM day_scenes WHERE scene_id = :sid AND day_id = :did"),
                {"sid": sc.id, "did": id_b},
            )).first()
            if ds_row:
                raw_edits.append({
                    "op": "patch", "entity": "day_scenes", "id": ds_row.id,
                    "fields": {"day_id": id_a},
                })

        if not raw_edits:
            return {"error": "No scenes found on either day to swap"}

        preview = await PropagationEngine.preview(
            project_id=self.project_id,
            user_id=self.user_id,
            raw_edits=raw_edits,
            session=self.session,
        )
        self._pg = None
        diff = dict(preview.diff or {})
        diff.pop("request", None)
        return {
            "batch_id": preview.batch_id,
            "expires_at": preview.expires_at.isoformat(),
            "diff": diff,
        }

    async def _get_flags(self, severity: str | None = None) -> dict:
        where = "WHERE project_id=:pid AND resolved_at IS NULL AND dismissed=FALSE"
        params: dict = {"pid": self.project_id}
        if severity:
            where += " AND severity=:sev"
            params["sev"] = severity

        rows = (await self.session.execute(
            sa.text(
                f"SELECT id, kind, severity, title, description, raised_at FROM flags {where} "
                "ORDER BY severity, raised_at DESC LIMIT 50"
            ),
            params,
        )).fetchall()

        return {
            "count": len(rows),
            "flags": [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "severity": r.severity,
                    "title": r.title,
                    "description": r.description,
                    "raised_at": r.raised_at.isoformat() if r.raised_at else None,
                }
                for r in rows
            ],
        }

    async def _commit_preview(self, batch_id: str) -> dict:
        from datetime import datetime, timezone
        import sqlalchemy as sa
        from .views.base import invalidate_views
        from .views import main_schedule as _ms
        from .views import calendar as _cal
        from .views import scenes_matrix as _sm
        from .views import cast_dood as _dood

        _renderers = {
            "main_schedule": _ms.render,
            "calendar": _cal.render,
            "scenes_matrix": _sm.render,
            "cast_dood": _dood.render,
        }

        result = await self.session.execute(
            sa.text(
                "SELECT id, project_id, diff, status, expires_at "
                "FROM propagation_previews WHERE batch_id=:bid"
            ),
            {"bid": batch_id},
        )
        row = result.first()
        if not row or row.project_id != self.project_id:
            return {"error": "Preview not found"}
        if row.status != "pending":
            return {"error": f"Preview is already {row.status}"}
        if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return {"error": "Preview has expired"}

        diff = row.diff or {}
        if diff.get("breaks"):
            return {"error": "Hard breaks prevent commit", "breaks": diff["breaks"]}

        raw_edits = (diff.get("request") or {}).get("edits", [])
        await edit_applicator.apply(self.project_id, raw_edits, self.session)

        await self.session.execute(
            sa.text(
                "UPDATE propagation_previews SET status='confirmed', confirmed_at=NOW() "
                "WHERE batch_id=:bid"
            ),
            {"bid": batch_id},
        )
        await self.session.execute(
            sa.text("UPDATE edits SET propagated=TRUE WHERE batch_id=:bid"),
            {"bid": batch_id},
        )

        project_row = (await self.session.execute(
            sa.text("SELECT live_scenario_id FROM projects WHERE id=:pid"),
            {"pid": self.project_id},
        )).first()
        scenario_id = project_row.live_scenario_id if project_row else None

        affected_views: list[str] = diff.get("views_affected", [])
        await invalidate_views(self.project_id, affected_views, scenario_id, self.session)
        await self.session.commit()
        self._pg = None

        return {
            "ok": True,
            "batch_id": batch_id,
            "views_affected": affected_views,
        }
