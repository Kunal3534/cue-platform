"""Fan out a parsed xlsx dict into the v1 relational tables for a new project.

Called by the v1 POST /projects route immediately after the project row is
inserted. Mirrors the logic in migration 003 but uses the async session.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Date helpers (duplicated from migration 003 — can't import Alembic files)
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _extract_year(window: str | None) -> int:
    if window:
        m = re.search(r"\b(20\d{2})\b", window)
        if m:
            return int(m.group(1))
    return date.today().year


def _parse_date(date_raw: str | None, year: int) -> date | None:
    if not date_raw:
        return None
    text = date_raw.lower()
    month_num = next((v for k, v in _MONTHS.items() if k in text), None)
    if month_num is None:
        return None
    dm = re.search(r"\b(\d{1,2})\b", text)
    if not dm:
        return None
    try:
        return date(year, month_num, int(dm.group(1)))
    except ValueError:
        return None


_CODE_KIND: dict[str, str] = {
    "L": "lighting", "DR": "drone", "SL": "steadi",
    "JJ": "jib", "GR": "grip", "VFX": "special",
}


def _infer_camera_kind(code: str) -> str:
    upper = code.upper()
    for prefix, kind in _CODE_KIND.items():
        if upper == prefix or (upper.startswith(prefix) and upper[len(prefix):].isdigit()):
            return kind
    return "camera"


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Ingestor
# ---------------------------------------------------------------------------

async def ingest(
    project_id: str,
    owner_id: str,
    parsed: dict,
    session: AsyncSession,
) -> str:
    """Fan out parsed dict into relational tables. Returns live_scenario_id."""
    window_str: str | None = parsed.get("window")
    year = _extract_year(window_str)
    days_data: list[dict] = parsed.get("days", [])
    cast_map: dict[str, str] = parsed.get("cast_map", {})
    unit_cols: list[str] = parsed.get("unit_cols", [])

    # ----------------------------------------------------------------
    # Locations
    # ----------------------------------------------------------------
    locations_map: dict[tuple[str, str], str] = {}
    for d in days_data:
        if not d.get("is_shoot"):
            continue
        area = (d.get("location") or "").strip()
        name = (d.get("film_location") or "").strip()
        key = (area, name)
        if key in locations_map or (not area and not name):
            continue
        text_lower = (name + area).lower()
        kind = (
            "ext" if any(w in text_lower for w in ("beach", "coast", "field", "road", "forest", "garden", "open"))
            else "studio" if any(w in text_lower for w in ("studio", "set"))
            else "ext"
        )
        loc_id = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO locations (id, project_id, name, area, kind, created_at, updated_at) "
                "VALUES (:id, :pid, :name, :area, :kind, NOW(), NOW())"
            ),
            {"id": loc_id, "pid": project_id, "name": name or area, "area": area, "kind": kind},
        )
        locations_map[key] = loc_id

    # ----------------------------------------------------------------
    # Characters
    # ----------------------------------------------------------------
    chars_map: dict[str, str] = {}
    for canonical, actor in cast_map.items():
        canonical_up = canonical.strip().upper()
        if canonical_up in chars_map:
            continue
        cid = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO characters "
                "(id, project_id, canonical_name, display_name, actor_name, is_principal, created_at, updated_at) "
                "VALUES (:id, :pid, :cn, :dn, :actor, TRUE, NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_characters_project_canonical DO NOTHING"
            ),
            {"id": cid, "pid": project_id, "cn": canonical_up,
             "dn": canonical.strip().title(), "actor": actor or None},
        )
        row = (await session.execute(
            sa.text("SELECT id FROM characters WHERE project_id=:pid AND canonical_name=:cn"),
            {"pid": project_id, "cn": canonical_up},
        )).first()
        chars_map[canonical_up] = row.id if row else cid

    # ----------------------------------------------------------------
    # Camera units
    # ----------------------------------------------------------------
    units_map: dict[str, str] = {}
    for code in unit_cols:
        code = code.strip()
        if not code or code.upper() == "JR":
            continue
        uid_val = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO camera_units "
                "(id, project_id, unit_code, kind, created_at, updated_at) "
                "VALUES (:id, :pid, :code, :kind, NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_camera_units_project_code DO NOTHING"
            ),
            {"id": uid_val, "pid": project_id, "code": code, "kind": _infer_camera_kind(code)},
        )
        row = (await session.execute(
            sa.text("SELECT id FROM camera_units WHERE project_id=:pid AND unit_code=:code"),
            {"pid": project_id, "code": code},
        )).first()
        units_map[code] = row.id if row else uid_val

    # ----------------------------------------------------------------
    # Days, scenes, junctions
    # ----------------------------------------------------------------
    vehicles_map: dict[str, str] = {}

    for idx, d in enumerate(days_data):
        is_shoot = bool(d.get("is_shoot"))
        shoot_no: int | None = d.get("shoot_day_no") if is_shoot else None
        # v0.1 parser uses shoot_day_no; migration 003 used shoot_day_number
        if shoot_no is None and is_shoot:
            shoot_no = d.get("shoot_day_number")

        day_date = _parse_date(d.get("date_raw"), year)
        if day_date is None:
            day_date = date(year, 1, 1) + timedelta(days=idx)

        area = (d.get("location") or "").strip()
        name = (d.get("film_location") or "").strip()
        loc_id = locations_map.get((area, name))

        day_id = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO days "
                "(id, project_id, shoot_day_number, date, kind, primary_location_id, created_at, updated_at) "
                "VALUES (:id, :pid, :sdn, :dt, :kind, :loc, NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_days_project_date DO NOTHING"
            ),
            {"id": day_id, "pid": project_id, "sdn": shoot_no,
             "dt": day_date, "kind": "shoot" if is_shoot else "off", "loc": loc_id},
        )
        row = (await session.execute(
            sa.text("SELECT id FROM days WHERE project_id=:pid AND date=:dt"),
            {"pid": project_id, "dt": day_date},
        )).first()
        day_id = row.id if row else day_id

        if not is_shoot:
            continue

        # Placeholder scene
        scene_number = f"D{shoot_no}-1"
        scene_id = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO scenes "
                "(id, project_id, scene_number, title, dn, location_id, sequence, status, created_at, updated_at) "
                "VALUES (:id, :pid, :sn, :title, 'day', :loc, :seq, 'planned', NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_scenes_project_number DO NOTHING"
            ),
            {"id": scene_id, "pid": project_id, "sn": scene_number,
             "title": name or area or f"Day {shoot_no}", "loc": loc_id, "seq": shoot_no},
        )
        row = (await session.execute(
            sa.text("SELECT id FROM scenes WHERE project_id=:pid AND scene_number=:sn"),
            {"pid": project_id, "sn": scene_number},
        )).first()
        scene_id = row.id if row else scene_id

        await session.execute(
            sa.text(
                "INSERT INTO day_scenes "
                "(id, day_id, scene_id, order_in_day, actual_status, created_at, updated_at) "
                "VALUES (:id, :did, :sid, 1, 'scheduled', NOW(), NOW()) "
                "ON CONFLICT ON CONSTRAINT uq_day_scenes DO NOTHING"
            ),
            {"id": _uid(), "did": day_id, "sid": scene_id},
        )

        # Scene characters
        cast_names: list[str] = d.get("cast") or []
        seen_chars: set[str] = set()
        for char_name in cast_names:
            cu = char_name.strip().upper()
            if not cu or cu in seen_chars:
                continue
            if cu not in chars_map:
                cid = _uid()
                await session.execute(
                    sa.text(
                        "INSERT INTO characters "
                        "(id, project_id, canonical_name, display_name, is_principal, created_at, updated_at) "
                        "VALUES (:id, :pid, :cn, :dn, FALSE, NOW(), NOW()) "
                        "ON CONFLICT ON CONSTRAINT uq_characters_project_canonical DO NOTHING"
                    ),
                    {"id": cid, "pid": project_id, "cn": cu, "dn": char_name.strip().title()},
                )
                row = (await session.execute(
                    sa.text("SELECT id FROM characters WHERE project_id=:pid AND canonical_name=:cn"),
                    {"pid": project_id, "cn": cu},
                )).first()
                chars_map[cu] = row.id if row else cid
            seen_chars.add(cu)
            await session.execute(
                sa.text(
                    "INSERT INTO scene_characters "
                    "(id, scene_id, character_id, role, created_at) "
                    "VALUES (:id, :sid, :cid, 'speaking', NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_scene_characters DO NOTHING"
                ),
                {"id": _uid(), "sid": scene_id, "cid": chars_map[cu]},
            )

        # Camera day uses
        units_used: dict = d.get("units") or {}
        for code, count in units_used.items():
            code = code.strip()
            if code.upper() == "JR" or code not in units_map:
                continue
            try:
                cnt = int(float(count))
            except (TypeError, ValueError):
                cnt = 1
            await session.execute(
                sa.text(
                    "INSERT INTO camera_day_uses "
                    "(id, camera_unit_id, day_id, count, created_at) "
                    "VALUES (:id, :cuid, :did, :cnt, NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_camera_day_uses DO NOTHING"
                ),
                {"id": _uid(), "cuid": units_map[code], "did": day_id, "cnt": cnt},
            )

        # JR calls
        jr_raw = units_used.get("JR") or units_used.get("jr")
        if jr_raw is not None:
            try:
                jr_count = int(float(jr_raw))
            except (TypeError, ValueError):
                jr_count = 0
            if jr_count > 0:
                await session.execute(
                    sa.text(
                        "INSERT INTO junior_artist_calls "
                        "(id, project_id, day_id, count, grade, status, created_at, updated_at) "
                        "VALUES (:id, :pid, :did, :cnt, 'junior', 'planned', NOW(), NOW()) "
                        "ON CONFLICT ON CONSTRAINT uq_jr_calls_day_grade DO NOTHING"
                    ),
                    {"id": _uid(), "pid": project_id, "did": day_id, "cnt": jr_count},
                )

        # Picture vehicles
        for pv_name in (d.get("picture_vehicles") or []):
            pv_name = str(pv_name).strip()
            if not pv_name:
                continue
            if pv_name not in vehicles_map:
                vid = _uid()
                await session.execute(
                    sa.text(
                        "INSERT INTO picture_vehicles "
                        "(id, project_id, name, created_at, updated_at) "
                        "VALUES (:id, :pid, :name, NOW(), NOW()) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {"id": vid, "pid": project_id, "name": pv_name},
                )
                vehicles_map[pv_name] = vid
            await session.execute(
                sa.text(
                    "INSERT INTO vehicle_day_uses "
                    "(id, vehicle_id, day_id, count, created_at) "
                    "VALUES (:id, :vid, :did, 1, NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_vehicle_day_uses DO NOTHING"
                ),
                {"id": _uid(), "vid": vehicles_map[pv_name], "did": day_id},
            )

    # ----------------------------------------------------------------
    # Live scenario
    # ----------------------------------------------------------------
    scenario_id = _uid()
    await session.execute(
        sa.text(
            "INSERT INTO scenarios "
            "(id, project_id, name, is_live, created_by, created_at, updated_at) "
            "VALUES (:id, :pid, 'Live plan', TRUE, :owner, NOW(), NOW())"
        ),
        {"id": scenario_id, "pid": project_id, "owner": owner_id},
    )

    await session.execute(
        sa.text(
            "UPDATE projects SET live_scenario_id = :sid, status = 'pre' WHERE id = :pid"
        ),
        {"sid": scenario_id, "pid": project_id},
    )

    await session.commit()
    return scenario_id
