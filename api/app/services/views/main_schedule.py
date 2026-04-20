"""main_schedule view renderer.

JSON shape (matches schedule.html stripboard):
{
  "view": "main_schedule",
  "project_id": "...",
  "scenario_id": "...|null",
  "computed_at": "...",
  "days": [
    {
      "day_id": "...",
      "date": "YYYY-MM-DD",
      "day_of_week": "Friday",
      "shoot_day_number": 1,       # null for non-shoot
      "kind": "shoot",
      "location": {"id":"...", "name":"...", "area":"...", "kind":"ext"} | null,
      "scenes": [
        {
          "scene_id": "...",
          "scene_number": "D1-1",
          "title": "...",
          "dn": "day",
          "page_eighths": null,
          "setups_est": 0,
          "order_in_day": 1
        }
      ],
      "cast": ["AARAV", "MEERA"],
      "camera_units": [{"unit_code": "A", "kind": "camera", "count": 1}],
      "jr_count": 40,
      "shift_start": null,
      "shift_end": null,
      "notes": null
    }
  ],
  "meta": {
    "total_days": 27,
    "shoot_days": 22,
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }
}
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .base import get_cached, save_cache

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def render(
    project_id: str,
    scenario_id: str | None,
    session: AsyncSession,
    use_cache: bool = True,
) -> dict:
    if use_cache:
        cached = await get_cached(project_id, "main_schedule", scenario_id, session)
        if cached:
            return cached

    # ----------------------------------------------------------------
    # 1. Days + locations
    # ----------------------------------------------------------------
    day_rows = (await session.execute(
        sa.text("""
            SELECT d.id, d.shoot_day_number, d.date, d.kind,
                   d.shift_start, d.shift_end, d.notes, d.banner_text,
                   l.id   AS loc_id,
                   l.name AS loc_name,
                   l.area AS loc_area,
                   l.kind AS loc_kind
            FROM days d
            LEFT JOIN locations l ON l.id = d.primary_location_id
            WHERE d.project_id = :pid
            ORDER BY d.date ASC
        """),
        {"pid": project_id},
    )).fetchall()

    # ----------------------------------------------------------------
    # 2. day_scenes → scenes
    # ----------------------------------------------------------------
    scene_rows = (await session.execute(
        sa.text("""
            SELECT ds.day_id, ds.order_in_day,
                   s.id AS scene_id, s.scene_number, s.title,
                   s.dn, s.page_eighths, s.setups_est
            FROM day_scenes ds
            JOIN scenes s ON s.id = ds.scene_id
            JOIN days d   ON d.id = ds.day_id
            WHERE d.project_id = :pid
            ORDER BY ds.day_id, ds.order_in_day
        """),
        {"pid": project_id},
    )).fetchall()

    # scene_id → list of canonical names
    sc_rows = (await session.execute(
        sa.text("""
            SELECT sc.scene_id, c.canonical_name
            FROM scene_characters sc
            JOIN characters c ON c.id = sc.character_id
            WHERE c.project_id = :pid
        """),
        {"pid": project_id},
    )).fetchall()

    # ----------------------------------------------------------------
    # 3. Camera day uses
    # ----------------------------------------------------------------
    cam_rows = (await session.execute(
        sa.text("""
            SELECT cdu.day_id, cu.unit_code, cu.kind, cdu.count
            FROM camera_day_uses cdu
            JOIN camera_units cu ON cu.id = cdu.camera_unit_id
            WHERE cu.project_id = :pid
        """),
        {"pid": project_id},
    )).fetchall()

    # ----------------------------------------------------------------
    # 4. JR counts per day
    # ----------------------------------------------------------------
    jr_rows = (await session.execute(
        sa.text("""
            SELECT day_id, SUM(count) AS total
            FROM junior_artist_calls
            WHERE project_id = :pid
            GROUP BY day_id
        """),
        {"pid": project_id},
    )).fetchall()

    # ----------------------------------------------------------------
    # Merge into lookup dicts
    # ----------------------------------------------------------------
    scene_chars: dict[str, list[str]] = defaultdict(list)
    for r in sc_rows:
        scene_chars[r.scene_id].append(r.canonical_name)

    scenes_by_day: dict[str, list[dict]] = defaultdict(list)
    for r in scene_rows:
        scenes_by_day[r.day_id].append({
            "scene_id": r.scene_id,
            "scene_number": r.scene_number,
            "title": r.title,
            "dn": r.dn,
            "page_eighths": r.page_eighths,
            "setups_est": r.setups_est or 0,
            "order_in_day": r.order_in_day,
        })

    # day cast = union of all scene chars on that day
    day_cast: dict[str, list[str]] = defaultdict(list)
    for day_id, scene_list in scenes_by_day.items():
        seen: set[str] = set()
        for s in scene_list:
            for cn in scene_chars.get(s["scene_id"], []):
                if cn not in seen:
                    seen.add(cn)
                    day_cast[day_id].append(cn)

    cam_by_day: dict[str, list[dict]] = defaultdict(list)
    for r in cam_rows:
        cam_by_day[r.day_id].append({
            "unit_code": r.unit_code,
            "kind": r.kind,
            "count": r.count,
        })

    jr_by_day: dict[str, int] = {r.day_id: int(r.total) for r in jr_rows}

    # ----------------------------------------------------------------
    # Build payload
    # ----------------------------------------------------------------
    days_out = []
    shoot_days = 0
    for r in day_rows:
        is_shoot = r.kind == "shoot"
        if is_shoot:
            shoot_days += 1
        loc = (
            {"id": r.loc_id, "name": r.loc_name, "area": r.loc_area, "kind": r.loc_kind}
            if r.loc_id else None
        )
        days_out.append({
            "day_id": r.id,
            "date": r.date.isoformat() if r.date else None,
            "day_of_week": _WEEKDAYS[r.date.weekday()] if r.date else None,
            "shoot_day_number": r.shoot_day_number,
            "kind": r.kind,
            "location": loc,
            "scenes": scenes_by_day.get(r.id, []),
            "cast": day_cast.get(r.id, []),
            "camera_units": cam_by_day.get(r.id, []),
            "jr_count": jr_by_day.get(r.id, 0),
            "shift_start": str(r.shift_start) if r.shift_start else None,
            "shift_end": str(r.shift_end) if r.shift_end else None,
            "notes": r.notes,
        })

    start_date = day_rows[0].date.isoformat() if day_rows else None
    end_date = day_rows[-1].date.isoformat() if day_rows else None

    payload = {
        "view": "main_schedule",
        "project_id": project_id,
        "scenario_id": scenario_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "days": days_out,
        "meta": {
            "total_days": len(day_rows),
            "shoot_days": shoot_days,
            "start_date": start_date,
            "end_date": end_date,
        },
    }

    await save_cache(project_id, "main_schedule", scenario_id, payload, session)
    await session.commit()
    return payload
