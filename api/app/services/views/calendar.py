"""calendar view renderer.

JSON shape (matches calendar.html month-grid):
{
  "view": "calendar",
  "project_id": "...",
  "scenario_id": "...|null",
  "computed_at": "...",
  "months": [
    {
      "label": "April 2026",
      "year": 2026,
      "month": 4,
      "days": [
        {
          "date": "2026-04-10",
          "day_of_week": "Friday",
          "kind": "shoot",
          "shoot_day_number": 1,
          "location": "Ratnagiri Beach",
          "scenes": [{"scene_number": "D1-1", "title": "Day 1", "dn": "day"}],
          "scene_count": 1,
          "page_eighths_total": null,
          "setups_total": 0,
          "jr_count": 40,
          "shift_start": null,
          "shift_end": null,
          "banner_text": null
        }
      ]
    }
  ],
  "unscheduled": []
}
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .base import get_cached, save_cache

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def render(
    project_id: str,
    scenario_id: str | None,
    session: AsyncSession,
    use_cache: bool = True,
) -> dict:
    if use_cache:
        cached = await get_cached(project_id, "calendar", scenario_id, session)
        if cached:
            return cached

    # Days with locations
    day_rows = (await session.execute(
        sa.text("""
            SELECT d.id, d.shoot_day_number, d.date, d.kind,
                   d.shift_start, d.shift_end, d.banner_text,
                   l.name AS loc_name
            FROM days d
            LEFT JOIN locations l ON l.id = d.primary_location_id
            WHERE d.project_id = :pid
            ORDER BY d.date ASC
        """),
        {"pid": project_id},
    )).fetchall()

    # Scenes per day
    scene_rows = (await session.execute(
        sa.text("""
            SELECT ds.day_id, s.scene_number, s.title, s.dn,
                   s.page_eighths, s.setups_est,
                   ds.estimated_start, ds.estimated_duration_minutes
            FROM day_scenes ds
            JOIN scenes s ON s.id = ds.scene_id
            JOIN days d   ON d.id = ds.day_id
            WHERE d.project_id = :pid
            ORDER BY ds.day_id, ds.order_in_day
        """),
        {"pid": project_id},
    )).fetchall()

    # JR counts
    jr_rows = (await session.execute(
        sa.text("""
            SELECT day_id, SUM(count) AS total
            FROM junior_artist_calls
            WHERE project_id = :pid
            GROUP BY day_id
        """),
        {"pid": project_id},
    )).fetchall()

    # Talent per day (editorial calendars lead with who is on site)
    talent_rows = (await session.execute(
        sa.text("""
            SELECT DISTINCT ds.day_id, c.display_name, c.is_principal
            FROM day_scenes ds
            JOIN scene_characters sc ON sc.scene_id = ds.scene_id
            JOIN characters c ON c.id = sc.character_id
            JOIN days d ON d.id = ds.day_id
            WHERE d.project_id = :pid
            ORDER BY ds.day_id, c.is_principal DESC, c.display_name
        """),
        {"pid": project_id},
    )).fetchall()

    scenes_by_day: dict[str, list[dict]] = defaultdict(list)
    for r in scene_rows:
        scenes_by_day[r.day_id].append({
            "scene_number": r.scene_number,
            "title": r.title,
            "dn": r.dn,
            "start": r.estimated_start.strftime("%H:%M") if r.estimated_start else None,
            "duration_minutes": r.estimated_duration_minutes,
        })

    jr_by_day: dict[str, int] = {r.day_id: int(r.total) for r in jr_rows}

    talent_by_day: dict[str, list[str]] = defaultdict(list)
    for r in talent_rows:
        talent_by_day[r.day_id].append(r.display_name)

    # Group days by (year, month)
    months_map: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in day_rows:
        d = r.date
        scene_list = scenes_by_day.get(r.id, [])
        page_eighths = sum(
            sr.page_eighths
            for sr in scene_rows
            if sr.day_id == r.id and sr.page_eighths is not None
        )
        setups = sum(
            sr.setups_est or 0
            for sr in scene_rows
            if sr.day_id == r.id
        )
        months_map[(d.year, d.month)].append({
            "date": d.isoformat(),
            "day_of_week": _WEEKDAYS[d.weekday()],
            "kind": r.kind,
            "shoot_day_number": r.shoot_day_number,
            "location": r.loc_name,
            "scenes": scene_list,
            "scene_count": len(scene_list),
            "page_eighths_total": page_eighths or None,
            "setups_total": setups,
            "jr_count": jr_by_day.get(r.id, 0),
            "talent": talent_by_day.get(r.id, []),
            "shift_start": str(r.shift_start) if r.shift_start else None,
            "shift_end": str(r.shift_end) if r.shift_end else None,
            "banner_text": r.banner_text,
        })

    months_out = [
        {
            "label": f"{_MONTH_NAMES[month]} {year}",
            "year": year,
            "month": month,
            "days": days,
        }
        for (year, month), days in sorted(months_map.items())
    ]

    # Unscheduled scenes (scenes with no day_scene link)
    unscheduled_rows = (await session.execute(
        sa.text("""
            SELECT s.scene_number, s.title, s.dn
            FROM scenes s
            WHERE s.project_id = :pid
              AND NOT EXISTS (
                  SELECT 1 FROM day_scenes ds WHERE ds.scene_id = s.id
              )
            ORDER BY s.scene_number
        """),
        {"pid": project_id},
    )).fetchall()

    payload = {
        "view": "calendar",
        "project_id": project_id,
        "scenario_id": scenario_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "months": months_out,
        "unscheduled": [
            {"scene_number": r.scene_number, "title": r.title, "dn": r.dn}
            for r in unscheduled_rows
        ],
    }

    await save_cache(project_id, "calendar", scenario_id, payload, session)
    await session.commit()
    return payload
