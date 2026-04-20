"""scenes_matrix view renderer.

JSON shape (matches scenes.html cross-tab):
{
  "view": "scenes_matrix",
  "project_id": "...",
  "scenario_id": "...|null",
  "computed_at": "...",
  "shoot_days": [
    {"day_id": "...", "shoot_day_number": 1, "date": "2026-04-10", "label": "D1"}
  ],
  "scenes": [
    {
      "scene_id": "...",
      "scene_number": "D1-1",
      "title": "...",
      "dn": "day",
      "page_eighths": null,
      "characters": ["AARAV"],
      "day_numbers": [1]          # shoot_day_number of each day this scene appears on
    }
  ],
  "meta": {
    "total_pages_eighths": 0,
    "day_count": 0,
    "night_count": 0,
    "ext_count": 0,
    "int_count": 0
  }
}
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .base import get_cached, save_cache


async def render(
    project_id: str,
    scenario_id: str | None,
    session: AsyncSession,
    use_cache: bool = True,
) -> dict:
    if use_cache:
        cached = await get_cached(project_id, "scenes_matrix", scenario_id, session)
        if cached:
            return cached

    # All shoot days ordered
    shoot_day_rows = (await session.execute(
        sa.text("""
            SELECT id, shoot_day_number, date
            FROM days
            WHERE project_id = :pid AND kind = 'shoot'
            ORDER BY date ASC
        """),
        {"pid": project_id},
    )).fetchall()

    shoot_day_ids: set[str] = {r.id for r in shoot_day_rows}
    day_num_by_id: dict[str, int] = {r.id: r.shoot_day_number for r in shoot_day_rows}

    # All scenes for project + which shoot days they appear on
    scene_day_rows = (await session.execute(
        sa.text("""
            SELECT s.id AS scene_id, s.scene_number, s.title,
                   s.dn, s.page_eighths, l.kind AS loc_kind,
                   ds.day_id
            FROM scenes s
            LEFT JOIN day_scenes ds ON ds.scene_id = s.id
            LEFT JOIN locations l   ON l.id = s.location_id
            WHERE s.project_id = :pid
            ORDER BY s.scene_number
        """),
        {"pid": project_id},
    )).fetchall()

    # Characters per scene
    char_rows = (await session.execute(
        sa.text("""
            SELECT sc.scene_id, c.canonical_name
            FROM scene_characters sc
            JOIN characters c ON c.id = sc.character_id
            WHERE c.project_id = :pid
        """),
        {"pid": project_id},
    )).fetchall()

    scene_chars: dict[str, list[str]] = defaultdict(list)
    for r in char_rows:
        scene_chars[r.scene_id].append(r.canonical_name)

    # Aggregate per scene
    scene_data: dict[str, dict] = {}
    for r in scene_day_rows:
        sid = r.scene_id
        if sid not in scene_data:
            scene_data[sid] = {
                "scene_id": sid,
                "scene_number": r.scene_number,
                "title": r.title,
                "dn": r.dn,
                "page_eighths": r.page_eighths,
                "loc_kind": r.loc_kind,
                "day_ids": [],
            }
        if r.day_id and r.day_id in shoot_day_ids:
            scene_data[sid]["day_ids"].append(r.day_id)

    # Build scenes output (deduplicated, sorted)
    seen_numbers: set[str] = set()
    scenes_out = []
    for sd in scene_data.values():
        if sd["scene_number"] in seen_numbers:
            continue
        seen_numbers.add(sd["scene_number"])
        day_numbers = sorted({
            day_num_by_id[did] for did in sd["day_ids"] if did in day_num_by_id
        })
        scenes_out.append({
            "scene_id": sd["scene_id"],
            "scene_number": sd["scene_number"],
            "title": sd["title"],
            "dn": sd["dn"],
            "page_eighths": sd["page_eighths"],
            "characters": scene_chars.get(sd["scene_id"], []),
            "day_numbers": day_numbers,
        })

    scenes_out.sort(key=lambda s: s["scene_number"])

    # Meta counts
    total_eighths = sum(s["page_eighths"] or 0 for s in scenes_out)
    day_count = sum(1 for s in scenes_out if s["dn"] in ("day", "dusk"))
    night_count = sum(1 for s in scenes_out if s["dn"] in ("night", "night_int"))
    ext_count = sum(
        1 for s in scenes_out if scene_data[s["scene_id"]]["loc_kind"] == "ext"
    )
    int_count = sum(
        1 for s in scenes_out if scene_data[s["scene_id"]]["loc_kind"] == "int"
    )

    payload = {
        "view": "scenes_matrix",
        "project_id": project_id,
        "scenario_id": scenario_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "shoot_days": [
            {
                "day_id": r.id,
                "shoot_day_number": r.shoot_day_number,
                "date": r.date.isoformat(),
                "label": f"D{r.shoot_day_number}",
            }
            for r in shoot_day_rows
        ],
        "scenes": scenes_out,
        "meta": {
            "total_pages_eighths": total_eighths,
            "day_count": day_count,
            "night_count": night_count,
            "ext_count": ext_count,
            "int_count": int_count,
        },
    }

    await save_cache(project_id, "scenes_matrix", scenario_id, payload, session)
    await session.commit()
    return payload
