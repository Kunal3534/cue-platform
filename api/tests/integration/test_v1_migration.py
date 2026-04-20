"""Integration test: apply migrations 001→003 against a live Postgres, upload the
Ratnagiri sample breakdown, and verify the expected row counts in v1 tables.

Run with:
    DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue pytest \
        tests/integration/test_v1_migration.py -v

Prerequisites:
  - Postgres running and reachable (docker-compose up db)
  - A clean database (or the test will recreate schema from scratch)
  - pytest + psycopg2-binary installed

The test uses a dedicated *test schema* (`public` wiped between runs) rather
than a separate database so it works with a single DB user and no superuser
privileges.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command as alembic_cmd
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

API_DIR = Path(__file__).parents[2]          # …/api
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_XLSX = FIXTURES_DIR / "ratnagiri_master.xlsx"
ALEMBIC_INI = API_DIR / "alembic.ini"

# ---------------------------------------------------------------------------
# DB URL — prefer env var so CI can override
# ---------------------------------------------------------------------------

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://cue:cue@localhost:5432/cue",
).replace("+asyncpg", "+psycopg2")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine(DB_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def migrated_db(sync_engine):
    """
    Drop all tables, run alembic upgrade 002 (schema only), insert the sample
    project via the parser, then run upgrade 003 (data + drop parsed_json).
    Returns an open connection for assertions.
    """
    # ---- wipe the DB so we start clean ----
    with sync_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    # ---- apply migrations 001 and 002 (schema) ----
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    alembic_cmd.upgrade(cfg, "002")

    # ---- insert test user + project using v0.1 parser ----
    from app.parser_service import parse_xlsx_bytes

    raw_xlsx = SAMPLE_XLSX.read_bytes()
    parsed = parse_xlsx_bytes(raw_xlsx)

    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"
            ),
            {"id": user_id, "email": "test@cue.dev", "name": "Test User"},
        )
        conn.execute(
            text(
                "INSERT INTO projects "
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

    # ---- apply migration 003: fan-out + drop parsed_json ----
    alembic_cmd.upgrade(cfg, "003")

    # ---- yield a connection for the test body ----
    with sync_engine.connect() as conn:
        yield conn, project_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count(conn, table: str, project_id: str | None = None) -> int:
    if project_id:
        row = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE project_id = :pid"),
            {"pid": project_id},
        ).scalar()
    else:
        row = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return int(row)


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

def test_v1_migration(migrated_db):
    conn, project_id = migrated_db

    # ---- parsed_json column must be gone ----
    col_exists = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='projects' AND column_name='parsed_json'"
        )
    ).first()
    assert col_exists is None, "parsed_json should have been dropped by migration 003"

    # ---- project row updated ----
    proj = conn.execute(
        text("SELECT live_scenario_id, status FROM projects WHERE id = :pid"),
        {"pid": project_id},
    ).first()
    assert proj is not None
    assert proj.live_scenario_id is not None, "live_scenario_id must be set"
    assert proj.status == "pre"

    # ---- one live scenario per project ----
    live_count = conn.execute(
        text("SELECT COUNT(*) FROM scenarios WHERE project_id=:pid AND is_live=TRUE"),
        {"pid": project_id},
    ).scalar()
    assert live_count == 1, f"expected exactly 1 live scenario, got {live_count}"

    # ---- days: every row in parsed_json becomes a day ----
    n_days = count(conn, "days", project_id)
    assert n_days > 0, "no days inserted"

    # ---- shoot days must have exactly one placeholder scene each ----
    n_shoot_days = conn.execute(
        text("SELECT COUNT(*) FROM days WHERE project_id=:pid AND kind='shoot'"),
        {"pid": project_id},
    ).scalar()
    n_scenes = count(conn, "scenes", project_id)
    assert n_scenes == n_shoot_days, (
        f"expected 1 scene per shoot day ({n_shoot_days}), got {n_scenes}"
    )

    # ---- each shoot day has exactly one day_scene link ----
    n_day_scenes = conn.execute(
        text(
            "SELECT COUNT(*) FROM day_scenes ds "
            "JOIN days d ON d.id = ds.day_id "
            "WHERE d.project_id = :pid"
        ),
        {"pid": project_id},
    ).scalar()
    assert int(n_day_scenes) == n_shoot_days, (
        f"expected {n_shoot_days} day_scene rows, got {n_day_scenes}"
    )

    # ---- characters: at least all cast_map entries ----
    n_chars = count(conn, "characters", project_id)
    assert n_chars > 0, "no characters inserted"

    # ---- camera_units: non-JR unit_cols ----
    n_units = count(conn, "camera_units", project_id)
    assert n_units > 0, "no camera_units inserted"

    # ---- locations: at least one unique location ----
    n_locs = count(conn, "locations", project_id)
    assert n_locs > 0, "no locations inserted"

    # ---- print a summary so the reviewer can verify numbers ----
    print(
        f"\n--- Migration row counts for project {project_id} ---\n"
        f"  days              : {n_days}\n"
        f"  shoot days        : {n_shoot_days}\n"
        f"  scenes            : {n_scenes}\n"
        f"  day_scenes        : {n_day_scenes}\n"
        f"  characters        : {n_chars}\n"
        f"  camera_units      : {n_units}\n"
        f"  locations         : {n_locs}\n"
        f"  live scenario set : {proj.live_scenario_id}\n"
    )


def test_migration_idempotent(migrated_db, sync_engine):
    """Running migration 003 a second time must be a no-op (exits cleanly)."""
    conn, project_id = migrated_db

    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)

    # Should not raise; idempotency guard returns early when parsed_json is gone
    alembic_cmd.upgrade(cfg, "003")

    # Row counts must not have changed
    n_days = count(conn, "days", project_id)
    assert n_days > 0


def test_v01_tables_still_exist(migrated_db):
    """After the migration the v0.1 share_tokens table must still be present."""
    conn, _ = migrated_db
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'share_tokens'"
        )
    ).first()
    assert result is not None, "share_tokens table should still exist"
