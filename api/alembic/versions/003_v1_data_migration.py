"""v1 data migration — fan out parsed_json into relational tables, then drop column

Revision ID: 003
Revises: 002
Create Date: 2026-04-20

For each existing project the algorithm is:
  1. Extract unique (area, film_location) pairs → locations rows
  2. Create characters from cast_map
  3. Create camera_units from unit_cols (excluding JR which is a jr call count)
  4. Create days rows; for each shoot day also create a placeholder scene,
     day_scene link, scene_characters, camera_day_uses, junior_artist_calls,
     and picture_vehicles / vehicle_day_uses
  5. Create the default live scenario and set projects.live_scenario_id
  6. Drop parsed_json column

Note: scene-level data doesn't exist in v0.1 uploads (Katakirr xlsx only has
day-level granularity).  The migration synthesises one placeholder scene per
shoot day so v1 edit flows have something to work with.  Real scene data
arrives via the scenes breakdown sheet in uploaded xlsx or via UI edits.

Idempotency
-----------
All INSERTs use ON CONFLICT DO NOTHING so re-running is safe.
An early guard checks whether parsed_json still exists; if not, the data phase
is skipped entirely (drop has already happened or migration was re-invoked).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Date parsing helpers
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
    return 2026


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


# ---------------------------------------------------------------------------
# Camera unit kind inference from unit code
# ---------------------------------------------------------------------------

_CODE_KIND: dict[str, str] = {
    "L": "lighting",
    "DR": "drone",
    "SL": "steadi",
    "JJ": "jib",
    "GR": "grip",
    "VFX": "special",
}


def _infer_camera_kind(code: str) -> str:
    upper = code.upper()
    for prefix, kind in _CODE_KIND.items():
        if upper == prefix or (upper.startswith(prefix) and upper[len(prefix):].isdigit()):
            return kind
    return "camera"


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def upgrade():
    conn = op.get_bind()

    # ----------------------------------------------------------------
    # Idempotency guard — if parsed_json was already dropped we have
    # nothing left to read; skip straight to the (no-op) DROP attempt.
    # ----------------------------------------------------------------
    parsed_json_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = 'parsed_json'"
        )
    ).first()

    if not parsed_json_exists:
        # Column already gone — migration was already applied.
        return

    rows = conn.execute(
        sa.text('SELECT id, owner_id, title, "window", parsed_json FROM projects')
    ).fetchall()

    for proj in rows:
        proj_id: str = proj.id
        owner_id: str = proj.owner_id
        raw = proj.parsed_json

        # psycopg2 returns JSON columns as dicts; guard for string fallback
        if isinstance(raw, str):
            pj: dict = json.loads(raw)
        elif isinstance(raw, dict):
            pj = raw
        else:
            continue  # unparseable — skip, project will be empty in v1

        window_str: str | None = pj.get("window") or proj.window
        year = _extract_year(window_str)
        days_data: list[dict] = pj.get("days", [])
        cast_map: dict[str, str] = pj.get("cast_map", {})
        unit_cols: list[str] = pj.get("unit_cols", [])

        # ----------------------------------------------------------------
        # 1. Locations — unique (area, film_location) pairs from shoot days
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

            text_lower = name.lower() + area.lower()
            if any(w in text_lower for w in ("beach", "coast", "field", "road", "forest", "garden", "open")):
                kind = "ext"
            elif any(w in text_lower for w in ("studio", "set")):
                kind = "studio"
            else:
                kind = "ext"

            loc_id = _new_id()
            conn.execute(
                sa.text(
                    "INSERT INTO locations "
                    "(id, project_id, name, area, kind, created_at, updated_at) "
                    "VALUES (:id, :pid, :name, :area, :kind, NOW(), NOW()) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": loc_id, "pid": proj_id, "name": name or area, "area": area, "kind": kind},
            )
            locations_map[key] = loc_id

        # ----------------------------------------------------------------
        # 2. Characters from cast_map
        # ----------------------------------------------------------------
        chars_map: dict[str, str] = {}  # canonical_upper → char_id
        for canonical, actor in cast_map.items():
            canonical_up = canonical.strip().upper()
            if canonical_up in chars_map:
                continue
            cid = _new_id()
            display = canonical.strip().title()
            conn.execute(
                sa.text(
                    "INSERT INTO characters "
                    "(id, project_id, canonical_name, display_name, actor_name, is_principal, created_at, updated_at) "
                    "VALUES (:id, :pid, :cn, :dn, :actor, TRUE, NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_characters_project_canonical DO NOTHING"
                ),
                {"id": cid, "pid": proj_id, "cn": canonical_up, "dn": display, "actor": actor or None},
            )
            # Re-fetch in case the ON CONFLICT fired and a different id already exists
            existing = conn.execute(
                sa.text(
                    "SELECT id FROM characters WHERE project_id=:pid AND canonical_name=:cn"
                ),
                {"pid": proj_id, "cn": canonical_up},
            ).first()
            chars_map[canonical_up] = existing.id if existing else cid

        # ----------------------------------------------------------------
        # 3. Camera units from unit_cols (skip JR — that's a JA count)
        # ----------------------------------------------------------------
        units_map: dict[str, str] = {}  # unit_code → camera_unit_id
        for code in unit_cols:
            code = code.strip()
            if not code or code.upper() == "JR":
                continue
            uid = _new_id()
            kind = _infer_camera_kind(code)
            conn.execute(
                sa.text(
                    "INSERT INTO camera_units "
                    "(id, project_id, unit_code, kind, created_at, updated_at) "
                    "VALUES (:id, :pid, :code, :kind, NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_camera_units_project_code DO NOTHING"
                ),
                {"id": uid, "pid": proj_id, "code": code, "kind": kind},
            )
            existing = conn.execute(
                sa.text(
                    "SELECT id FROM camera_units WHERE project_id=:pid AND unit_code=:code"
                ),
                {"pid": proj_id, "code": code},
            ).first()
            units_map[code] = existing.id if existing else uid

        # ----------------------------------------------------------------
        # 4. Days, placeholder scenes, junctions
        # ----------------------------------------------------------------
        vehicles_map: dict[str, str] = {}  # vehicle name → picture_vehicle_id

        for idx, d in enumerate(days_data):
            is_shoot: bool = bool(d.get("is_shoot"))
            shoot_no: int | None = d.get("shoot_day_no") if is_shoot else None

            day_date = _parse_date(d.get("date_raw"), year)
            if day_date is None:
                day_date = date(year, 1, 1) + timedelta(days=idx)

            kind_val = "shoot" if is_shoot else "off"
            area = (d.get("location") or "").strip()
            name = (d.get("film_location") or "").strip()
            loc_id = locations_map.get((area, name))

            day_id = _new_id()
            conn.execute(
                sa.text(
                    "INSERT INTO days "
                    "(id, project_id, shoot_day_number, date, kind, primary_location_id, created_at, updated_at) "
                    "VALUES (:id, :pid, :sdn, :dt, :kind, :loc, NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_days_project_date DO NOTHING"
                ),
                {
                    "id": day_id, "pid": proj_id,
                    "sdn": shoot_no, "dt": day_date,
                    "kind": kind_val, "loc": loc_id,
                },
            )
            # Re-fetch canonical day_id (ON CONFLICT may have kept an earlier row)
            existing_day = conn.execute(
                sa.text("SELECT id FROM days WHERE project_id=:pid AND date=:dt"),
                {"pid": proj_id, "dt": day_date},
            ).first()
            day_id = existing_day.id if existing_day else day_id

            if not is_shoot:
                continue

            # ---- placeholder scene ----
            scene_number = f"D{shoot_no}-1"
            scene_id = _new_id()
            conn.execute(
                sa.text(
                    "INSERT INTO scenes "
                    "(id, project_id, scene_number, title, dn, location_id, sequence, status, created_at, updated_at) "
                    "VALUES (:id, :pid, :sn, :title, 'day', :loc, :seq, 'planned', NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_scenes_project_number DO NOTHING"
                ),
                {
                    "id": scene_id, "pid": proj_id,
                    "sn": scene_number,
                    "title": name or area or f"Day {shoot_no}",
                    "loc": loc_id, "seq": shoot_no,
                },
            )
            existing_scene = conn.execute(
                sa.text("SELECT id FROM scenes WHERE project_id=:pid AND scene_number=:sn"),
                {"pid": proj_id, "sn": scene_number},
            ).first()
            scene_id = existing_scene.id if existing_scene else scene_id

            conn.execute(
                sa.text(
                    "INSERT INTO day_scenes "
                    "(id, day_id, scene_id, order_in_day, actual_status, created_at, updated_at) "
                    "VALUES (:id, :did, :sid, 1, 'scheduled', NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_day_scenes DO NOTHING"
                ),
                {"id": _new_id(), "did": day_id, "sid": scene_id},
            )

            # ---- scene_characters ----
            cast_names: list[str] = d.get("cast") or []
            seen_chars: set[str] = set()
            for char_name in cast_names:
                canonical_up = char_name.strip().upper()
                if not canonical_up or canonical_up in seen_chars:
                    continue
                # Create character on-the-fly if absent from cast_map
                if canonical_up not in chars_map:
                    cid = _new_id()
                    conn.execute(
                        sa.text(
                            "INSERT INTO characters "
                            "(id, project_id, canonical_name, display_name, is_principal, created_at, updated_at) "
                            "VALUES (:id, :pid, :cn, :dn, FALSE, NOW(), NOW()) "
                            "ON CONFLICT ON CONSTRAINT uq_characters_project_canonical DO NOTHING"
                        ),
                        {"id": cid, "pid": proj_id, "cn": canonical_up, "dn": char_name.strip().title()},
                    )
                    existing = conn.execute(
                        sa.text("SELECT id FROM characters WHERE project_id=:pid AND canonical_name=:cn"),
                        {"pid": proj_id, "cn": canonical_up},
                    ).first()
                    chars_map[canonical_up] = existing.id if existing else cid

                char_id = chars_map[canonical_up]
                seen_chars.add(canonical_up)
                conn.execute(
                    sa.text(
                        "INSERT INTO scene_characters "
                        "(id, scene_id, character_id, role, created_at) "
                        "VALUES (:id, :sid, :cid, 'speaking', NOW()) "
                        "ON CONFLICT ON CONSTRAINT uq_scene_characters DO NOTHING"
                    ),
                    {"id": _new_id(), "sid": scene_id, "cid": char_id},
                )

            # ---- camera_day_uses ----
            units_used: dict[str, object] = d.get("units") or {}
            for code, count in units_used.items():
                code = code.strip()
                if code.upper() == "JR" or code not in units_map:
                    continue
                try:
                    cnt = int(float(count))
                except (TypeError, ValueError):
                    cnt = 1
                conn.execute(
                    sa.text(
                        "INSERT INTO camera_day_uses "
                        "(id, camera_unit_id, day_id, count, created_at) "
                        "VALUES (:id, :cuid, :did, :cnt, NOW()) "
                        "ON CONFLICT ON CONSTRAINT uq_camera_day_uses DO NOTHING"
                    ),
                    {"id": _new_id(), "cuid": units_map[code], "did": day_id, "cnt": cnt},
                )

            # ---- junior_artist_calls ----
            jr_raw = units_used.get("JR") or units_used.get("jr")
            if jr_raw is not None:
                try:
                    jr_count = int(float(jr_raw))
                except (TypeError, ValueError):
                    jr_count = 0
                if jr_count > 0:
                    conn.execute(
                        sa.text(
                            "INSERT INTO junior_artist_calls "
                            "(id, project_id, day_id, count, grade, status, created_at, updated_at) "
                            "VALUES (:id, :pid, :did, :cnt, 'junior', 'planned', NOW(), NOW()) "
                            "ON CONFLICT ON CONSTRAINT uq_jr_calls_day_grade DO NOTHING"
                        ),
                        {"id": _new_id(), "pid": proj_id, "did": day_id, "cnt": jr_count},
                    )

            # ---- picture_vehicles ----
            for pv_name in (d.get("picture_vehicles") or []):
                pv_name = str(pv_name).strip()
                if not pv_name:
                    continue
                if pv_name not in vehicles_map:
                    vid = _new_id()
                    conn.execute(
                        sa.text(
                            "INSERT INTO picture_vehicles "
                            "(id, project_id, name, created_at, updated_at) "
                            "VALUES (:id, :pid, :name, NOW(), NOW()) "
                            "ON CONFLICT (id) DO NOTHING"
                        ),
                        {"id": vid, "pid": proj_id, "name": pv_name},
                    )
                    vehicles_map[pv_name] = vid

                vid = vehicles_map[pv_name]
                conn.execute(
                    sa.text(
                        "INSERT INTO vehicle_day_uses "
                        "(id, vehicle_id, day_id, count, created_at) "
                        "VALUES (:id, :vid, :did, 1, NOW()) "
                        "ON CONFLICT ON CONSTRAINT uq_vehicle_day_uses DO NOTHING"
                    ),
                    {"id": _new_id(), "vid": vid, "did": day_id},
                )

        # ----------------------------------------------------------------
        # 5. Default live scenario + update projects.live_scenario_id
        # ----------------------------------------------------------------
        # Only create if no live scenario exists for this project yet
        existing_live = conn.execute(
            sa.text(
                "SELECT id FROM scenarios WHERE project_id=:pid AND is_live=TRUE"
            ),
            {"pid": proj_id},
        ).first()

        if not existing_live:
            scenario_id = _new_id()
            conn.execute(
                sa.text(
                    "INSERT INTO scenarios "
                    "(id, project_id, name, is_live, created_by, created_at, updated_at) "
                    "VALUES (:id, :pid, 'Live plan', TRUE, :owner, NOW(), NOW()) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"id": scenario_id, "pid": proj_id, "owner": owner_id},
            )
        else:
            scenario_id = existing_live.id

        conn.execute(
            sa.text("UPDATE projects SET live_scenario_id = :sid WHERE id = :pid"),
            {"sid": scenario_id, "pid": proj_id},
        )

    # ----------------------------------------------------------------
    # 6. Drop parsed_json
    #    v0.1 routes that read this column will break after this point;
    #    they are replaced by v1 routes in Week 2.
    # ----------------------------------------------------------------
    op.drop_column("projects", "parsed_json")


def downgrade():
    op.add_column(
        "projects",
        sa.Column("parsed_json", sa.JSON, nullable=True),
    )
    # Data cannot be reconstructed from normalised tables; leave NULL.
    # This is only intended for dev/CI rollback scenarios.
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM scenarios WHERE name = 'Live plan' AND is_live = TRUE"
    ))
    conn.execute(sa.text("UPDATE projects SET live_scenario_id = NULL"))
