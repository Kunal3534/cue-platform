"""cast_dood (Days Out Of Days) view renderer.

W = working that shoot day (has scenes)
H = on hold (between first and last working day, not working)
· = off (before first or after last working day, or never works)

JSON shape (matches cast.html DOOD table):
{
  "view": "cast_dood",
  "project_id": "...",
  "scenario_id": "...|null",
  "computed_at": "...",
  "shoot_days": [
    {"day_id": "...", "shoot_day_number": 1, "date": "2026-04-10", "label": "D1"}
  ],
  "characters": [
    {
      "character_id": "...",
      "canonical_name": "AARAV",
      "display_name": "Aarav",
      "actor_name": "SIDDHARTH CHANDEKAR",
      "is_principal": true,
      "days": {"1": "W", "2": "H", "3": "."},   # keyed by shoot_day_number (str)
      "summary": {"W": 17, "H": 3, "T": 0}
    }
  ],
  "day_totals": {"1": 5, "2": 4}   # cast working per shoot day
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
        cached = await get_cached(project_id, "cast_dood", scenario_id, session)
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

    shoot_day_numbers: list[int] = [r.shoot_day_number for r in shoot_day_rows]
    day_id_to_num: dict[str, int] = {r.id: r.shoot_day_number for r in shoot_day_rows}

    # All characters for the project
    char_rows = (await session.execute(
        sa.text("""
            SELECT id, canonical_name, display_name, actor_name, is_principal
            FROM characters
            WHERE project_id = :pid
            ORDER BY is_principal DESC, canonical_name ASC
        """),
        {"pid": project_id},
    )).fetchall()

    # Character appearances on shoot days (via scene_characters)
    appearance_rows = (await session.execute(
        sa.text("""
            SELECT DISTINCT d.shoot_day_number, c.id AS char_id
            FROM days d
            JOIN day_scenes ds   ON ds.day_id = d.id
            JOIN scenes s        ON s.id = ds.scene_id
            JOIN scene_characters sc ON sc.scene_id = s.id
            JOIN characters c    ON c.id = sc.character_id
            WHERE d.project_id = :pid AND d.kind = 'shoot'
        """),
        {"pid": project_id},
    )).fetchall()

    # char_id → set of shoot_day_numbers where they work (W)
    working_days: dict[str, set[int]] = defaultdict(set)
    for r in appearance_rows:
        working_days[r.char_id].add(r.shoot_day_number)

    # day_totals: shoot_day_number → count of working characters
    day_totals: dict[str, int] = defaultdict(int)

    characters_out = []
    for c in char_rows:
        w_days = sorted(working_days.get(c.id, set()))
        if not w_days:
            # Never appears — all dots
            days_status = {str(n): "." for n in shoot_day_numbers}
            summary = {"W": 0, "H": 0, "T": 0}
        else:
            first_w = min(w_days)
            last_w = max(w_days)
            days_status: dict[str, str] = {}
            w_count = h_count = 0
            for sdn in shoot_day_numbers:
                if sdn in w_days:
                    days_status[str(sdn)] = "W"
                    w_count += 1
                    day_totals[str(sdn)] += 1
                elif first_w <= sdn <= last_w:
                    days_status[str(sdn)] = "H"
                    h_count += 1
                else:
                    days_status[str(sdn)] = "."
            summary = {"W": w_count, "H": h_count, "T": 0}

        characters_out.append({
            "character_id": c.id,
            "canonical_name": c.canonical_name,
            "display_name": c.display_name,
            "actor_name": c.actor_name,
            "is_principal": c.is_principal,
            "days": days_status,
            "summary": summary,
        })

    payload = {
        "view": "cast_dood",
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
        "characters": characters_out,
        "day_totals": dict(day_totals),
    }

    await save_cache(project_id, "cast_dood", scenario_id, payload, session)
    await session.commit()
    return payload
