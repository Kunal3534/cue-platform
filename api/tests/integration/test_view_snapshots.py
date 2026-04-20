"""Snapshot tests for the four v1 views against the Ratnagiri fixture.

Run with:
    DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue pytest \
        tests/integration/test_view_snapshots.py -v -s

To re-bless all snapshots:
    BLESS=1 DATABASE_URL=... pytest tests/integration/test_view_snapshots.py -v

Each test:
  1. Renders the view against the migrated Ratnagiri DB.
  2. Normalises the payload (strips volatile fields: computed_at, UUIDs).
  3. Compares against the saved snapshot in tests/snapshots/.
  4. If the snapshot is missing, saves it (first-run bless mode).

If the view payload changes shape, delete the relevant snapshot file and
re-run with BLESS=1.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command as alembic_cmd
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

API_DIR      = Path(__file__).parents[2]
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_XLSX  = FIXTURES_DIR / "ratnagiri_master.xlsx"
ALEMBIC_INI  = API_DIR / "alembic.ini"
SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"
SNAPSHOTS_DIR.mkdir(exist_ok=True)

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://cue:cue@localhost:5432/cue",
).replace("+asyncpg", "+psycopg2")

ASYNC_DB_URL = DB_URL.replace("+psycopg2", "+asyncpg")

# ---------------------------------------------------------------------------
# Module-scoped DB fixture (independent from test_v1_migration)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def snapshot_db():
    """
    Wipe schema → run 001+002 → insert Ratnagiri project → run 003.
    Returns (project_id,).
    """
    import uuid as _uuid

    engine = create_engine(DB_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    alembic_cmd.upgrade(cfg, "002")

    from app.parser_service import parse_xlsx_bytes

    raw_xlsx = SAMPLE_XLSX.read_bytes()
    parsed   = parse_xlsx_bytes(raw_xlsx)

    user_id    = str(_uuid.uuid4())
    project_id = str(_uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
            {"id": user_id, "email": "snap@cue.dev", "name": "Snap User"},
        )
        conn.execute(
            text(
                'INSERT INTO projects '
                '(id, owner_id, title, "window", source_file, parsed_json) '
                "VALUES (:id, :uid, :title, :window, :src, CAST(:pj AS JSON))"
            ),
            {
                "id": project_id,
                "uid": user_id,
                "title": parsed["title"],
                "window": parsed.get("window", ""),
                "src": raw_xlsx,
                "pj": json.dumps(parsed),
            },
        )

    alembic_cmd.upgrade(cfg, "003")

    yield project_id

    engine.dispose()


# ---------------------------------------------------------------------------
# Normalisation helper
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_VOLATILE_KEYS = frozenset({"computed_at", "project_id", "scenario_id"})


def _normalise(obj: object) -> object:
    if isinstance(obj, str):
        return "UUID" if _UUID_RE.match(obj) else obj
    if isinstance(obj, dict):
        return {
            k: "..." if k in _VOLATILE_KEYS else _normalise(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalise(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Async view runner
# ---------------------------------------------------------------------------

async def _render(view_name: str, project_id: str) -> dict:
    from app.services.views import main_schedule, calendar, scenes_matrix, cast_dood

    _renderers = {
        "main_schedule": main_schedule.render,
        "calendar":      calendar.render,
        "scenes_matrix": scenes_matrix.render,
        "cast_dood":     cast_dood.render,
    }

    engine = create_async_engine(ASYNC_DB_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await _renderers[view_name](project_id, None, session, use_cache=False)
    await engine.dispose()
    return result


def _run(view_name: str, project_id: str) -> dict:
    return asyncio.run(_render(view_name, project_id))


# ---------------------------------------------------------------------------
# Snapshot assertion helper
# ---------------------------------------------------------------------------

def _check_snapshot(view_name: str, payload: dict) -> None:
    snapshot_path = SNAPSHOTS_DIR / f"{view_name}.json"
    normalised = _normalise(payload)

    bless = os.environ.get("BLESS", "").strip()

    if not snapshot_path.exists() or bless:
        snapshot_path.write_text(json.dumps(normalised, indent=2, default=str))
        print(f"\n  [snapshot] Blessed {snapshot_path.name}")
        return

    expected = json.loads(snapshot_path.read_text())
    assert normalised == expected, (
        f"Snapshot mismatch for '{view_name}'. "
        "Run with BLESS=1 to re-bless if the change is intentional."
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_main_schedule_snapshot(snapshot_db):
    project_id = snapshot_db
    payload = _run("main_schedule", project_id)

    assert payload["view"] == "main_schedule"
    assert payload["meta"]["shoot_days"] > 0
    assert len(payload["days"]) > 0

    _check_snapshot("main_schedule", payload)
    print(f"\n  days={payload['meta']['total_days']}  shoot={payload['meta']['shoot_days']}")


def test_calendar_snapshot(snapshot_db):
    project_id = snapshot_db
    payload = _run("calendar", project_id)

    assert payload["view"] == "calendar"
    assert len(payload["months"]) > 0

    _check_snapshot("calendar", payload)
    total_days = sum(len(m["days"]) for m in payload["months"])
    print(f"\n  months={len(payload['months'])}  days={total_days}")


def test_scenes_matrix_snapshot(snapshot_db):
    project_id = snapshot_db
    payload = _run("scenes_matrix", project_id)

    assert payload["view"] == "scenes_matrix"
    assert len(payload["shoot_days"]) > 0
    assert len(payload["scenes"]) > 0

    _check_snapshot("scenes_matrix", payload)
    print(f"\n  shoot_days={len(payload['shoot_days'])}  scenes={len(payload['scenes'])}")


def test_cast_dood_snapshot(snapshot_db):
    project_id = snapshot_db
    payload = _run("cast_dood", project_id)

    assert payload["view"] == "cast_dood"
    assert len(payload["shoot_days"]) > 0
    assert len(payload["characters"]) > 0

    _check_snapshot("cast_dood", payload)
    chars_with_w = sum(1 for c in payload["characters"] if c["summary"]["W"] > 0)
    print(f"\n  characters={len(payload['characters'])}  working={chars_with_w}")
