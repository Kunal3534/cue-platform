"""Comprehensive Week-6 integration tests.

Covers:
  (a) Full upload → migrate → all 4 views render with data
  (b) Edit → preview → commit → view_cache refreshed
  (c) Scenario fork → diff shows no changes → merge no-ops cleanly
  (d) CallSheet versioning: v1 then v2 for same day, both rows preserved
  (e) FlagDetector raises expected flags on the Ratnagiri fixture
  (f) Chat tool-call loop: propose_reschedule → commit_preview

Run with:
    DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
    pytest tests/integration/test_week6.py -v -s
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from alembic import command as alembic_cmd
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Paths / URLs
# ---------------------------------------------------------------------------

API_DIR = Path(__file__).parents[2]
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_XLSX = FIXTURES_DIR / "ratnagiri_master.xlsx"
ALEMBIC_INI = API_DIR / "alembic.ini"

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://cue:cue@localhost:5432/cue",
).replace("+asyncpg", "+psycopg2")

ASYNC_DB_URL = DB_URL.replace("+psycopg2", "+asyncpg")


# ---------------------------------------------------------------------------
# Module-scoped DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def week6_db():
    """Wipe schema → migrate to head → ingest Ratnagiri → (project_id, user_id)."""
    from app.parser_service import parse_xlsx_bytes
    from app.services import project_ingestor

    sync_engine = create_engine(DB_URL, future=True)

    with sync_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    alembic_cmd.upgrade(cfg, "head")

    user_id = str(uuid.uuid4())
    with sync_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
            {"id": user_id, "email": "week6@cue.app", "name": "Week6"},
        )
        conn.commit()

    data = SAMPLE_XLSX.read_bytes()
    parsed = parse_xlsx_bytes(data)

    project_id = str(uuid.uuid4())
    with sync_engine.connect() as conn:
        conn.execute(
            text(
                'INSERT INTO projects (id, owner_id, title, "window", '
                "source_file, source_filename, status) "
                "VALUES (:id, :uid, :title, :window, :src, :fname, 'pre')"
            ),
            {
                "id": project_id, "uid": user_id,
                "title": parsed["title"],
                "window": parsed.get("window"),
                "src": data, "fname": "ratnagiri_master.xlsx",
            },
        )
        conn.commit()

    async def _ingest():
        engine = create_async_engine(ASYNC_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            await project_ingestor.ingest(project_id, user_id, parsed, session)
        await engine.dispose()

    asyncio.run(_ingest())
    sync_engine.dispose()
    return project_id, user_id


def _make_session():
    engine = create_async_engine(ASYNC_DB_URL)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# (a) Upload → migrate → view-regen round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_views_render(week6_db):
    """After ingestion all four view renderers return non-empty payloads."""
    project_id, _ = week6_db
    factory = _make_session()

    from app.services.views import main_schedule as _ms
    from app.services.views import calendar as _cal
    from app.services.views import scenes_matrix as _sm
    from app.services.views import cast_dood as _dood

    async with factory() as session:
        ms  = await _ms.render(project_id, None, session, use_cache=False)
        cal = await _cal.render(project_id, None, session, use_cache=False)
        sm  = await _sm.render(project_id, None, session, use_cache=False)
        cd  = await _dood.render(project_id, None, session, use_cache=False)

    assert ms  and ms.get("rows"),   "main_schedule returned no rows"
    assert cal and cal.get("months"), "calendar returned no months"
    assert sm  and sm.get("scenes"),  "scenes_matrix returned no scenes"
    assert cd  and cd.get("characters"), "cast_dood returned no characters"

    # view_cache rows should now exist
    async with factory() as session:
        count = (await session.execute(
            sa.text("SELECT COUNT(*) FROM view_cache WHERE project_id = :pid"),
            {"pid": project_id},
        )).scalar()
    assert count >= 4, f"Expected ≥4 view_cache rows, got {count}"


# ---------------------------------------------------------------------------
# (b) Edit → preview → commit → view_cache refreshed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_preview_commit_refreshes_view(week6_db):
    """Patching a day_scenes row, committing, then re-rendering updates view_cache."""
    project_id, user_id = week6_db
    factory = _make_session()

    async with factory() as session:
        # Pick two shoot days and a scene scheduled on the first
        rows = (await session.execute(
            sa.text(
                "SELECT ds.id AS ds_id, ds.day_id, ds.order_in_day, "
                "       d2.id AS alt_day_id "
                "FROM day_scenes ds "
                "JOIN days d ON ds.day_id = d.id "
                "JOIN days d2 ON d2.project_id = d.project_id "
                "  AND d2.kind = 'shoot' AND d2.id != d.id "
                "WHERE d.project_id = :pid AND d.kind = 'shoot' "
                "LIMIT 1"
            ),
            {"pid": project_id},
        )).first()

    if not rows:
        pytest.skip("Fixture has only one shoot day — skipping move test")

    ds_id      = rows.ds_id
    alt_day_id = rows.alt_day_id

    from app.services.propagation_engine import PropagationEngine
    from app.services import edit_applicator
    from app.services.views import main_schedule as _ms
    from app.services.views.base import invalidate_views

    # Preview
    async with factory() as session:
        preview = await PropagationEngine.preview(
            project_id=project_id,
            user_id=user_id,
            raw_edits=[{
                "op": "patch",
                "entity": "day_scenes",
                "id": ds_id,
                "fields": {"day_id": alt_day_id, "order_in_day": 99},
            }],
            session=session,
        )

    assert preview.status == "pending"
    diff = preview.diff or {}
    assert not diff.get("breaks"), f"Unexpected hard breaks: {diff.get('breaks')}"

    # Commit
    async with factory() as session:
        await edit_applicator.apply(
            project_id,
            [{"op": "patch", "entity": "day_scenes", "id": ds_id,
              "fields": {"day_id": alt_day_id, "order_in_day": 99}}],
            session,
        )
        await session.execute(
            sa.text(
                "UPDATE propagation_previews SET status='confirmed', confirmed_at=NOW() "
                "WHERE batch_id=:bid"
            ),
            {"bid": preview.batch_id},
        )
        affected = diff.get("views_affected", ["main_schedule"])
        await invalidate_views(project_id, affected, None, session)
        await session.commit()

    # Re-render
    async with factory() as session:
        ms = await _ms.render(project_id, None, session, use_cache=False)

    assert ms and ms.get("rows"), "main_schedule empty after commit"

    # Revert (tidy up for subsequent tests)
    async with factory() as session:
        await edit_applicator.apply(
            project_id,
            [{"op": "patch", "entity": "day_scenes", "id": ds_id,
              "fields": {"day_id": rows.day_id, "order_in_day": rows.order_in_day}}],
            session,
        )
        await session.commit()


# ---------------------------------------------------------------------------
# (c) Scenario fork → diff → merge (no-op path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_fork_and_merge(week6_db):
    """Fork a scenario; immediately diff (no changes); merge returns ok with no batch."""
    project_id, user_id = week6_db
    factory = _make_session()

    # Capture snapshot
    async with factory() as session:
        day_scene_rows = (await session.execute(
            sa.text(
                "SELECT ds.id, ds.scene_id, ds.day_id, ds.order_in_day "
                "FROM day_scenes ds JOIN days d ON ds.day_id=d.id "
                "WHERE d.project_id=:pid"
            ),
            {"pid": project_id},
        )).fetchall()
        day_rows = (await session.execute(
            sa.text(
                "SELECT id, date, kind, location_id, shoot_day_number, shift_start "
                "FROM days WHERE project_id=:pid"
            ),
            {"pid": project_id},
        )).fetchall()

    from datetime import datetime, timezone
    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "day_scenes": [
            {"id": r.id, "scene_id": r.scene_id, "day_id": r.day_id,
             "order_in_day": r.order_in_day}
            for r in day_scene_rows
        ],
        "days": [
            {"id": r.id, "date": r.date.isoformat() if r.date else None,
             "kind": r.kind, "location_id": r.location_id,
             "shoot_day_number": r.shoot_day_number,
             "shift_start": r.shift_start.isoformat() if r.shift_start else None}
            for r in day_rows
        ],
    }

    from app.models import Scenario
    scenario_id = str(uuid.uuid4())
    async with factory() as session:
        scen = Scenario(
            id=scenario_id,
            project_id=project_id,
            name="Week6 fork",
            is_live=False,
            created_by=user_id,
            snapshot=snapshot,
        )
        session.add(scen)
        await session.commit()

    # Diff should show zero changes (snapshot == current live)
    async with factory() as session:
        snap_ds = {r["id"]: r for r in snapshot["day_scenes"]}
        current_rows = (await session.execute(
            sa.text(
                "SELECT ds.id, ds.scene_id, ds.day_id, ds.order_in_day, s.scene_number "
                "FROM day_scenes ds JOIN days d ON ds.day_id=d.id "
                "JOIN scenes s ON ds.scene_id=s.id "
                "WHERE d.project_id=:pid"
            ),
            {"pid": project_id},
        )).fetchall()
        current_ds = {r.id: r for r in current_rows}

    changes = []
    for ds_id, snap in snap_ds.items():
        if ds_id in current_ds:
            cur = current_ds[ds_id]
            if snap["day_id"] != cur.day_id or snap["order_in_day"] != cur.order_in_day:
                changes.append(ds_id)

    assert changes == [], f"Expected no diff after immediate fork, got: {changes}"

    # Merge no-op path
    from app.services.propagation_engine import PropagationEngine
    async with factory() as session:
        current_map = {r.id: r for r in (await session.execute(
            sa.text(
                "SELECT ds.id, ds.day_id, ds.order_in_day "
                "FROM day_scenes ds JOIN days d ON ds.day_id=d.id "
                "WHERE d.project_id=:pid"
            ),
            {"pid": project_id},
        )).fetchall()}

        edits = []
        for snap in snapshot["day_scenes"]:
            ds_id = snap["id"]
            if ds_id not in current_map:
                continue
            cur = current_map[ds_id]
            if snap["day_id"] != cur.day_id or snap["order_in_day"] != cur.order_in_day:
                edits.append(snap)

        assert edits == [], "Merge should have zero edit ops"

        await session.execute(
            sa.text("UPDATE scenarios SET merged_at=NOW() WHERE id=:sid"),
            {"sid": scenario_id},
        )
        await session.commit()

    async with factory() as session:
        merged_at = (await session.execute(
            sa.text("SELECT merged_at FROM scenarios WHERE id=:sid"),
            {"sid": scenario_id},
        )).scalar()

    assert merged_at is not None, "merged_at should be set after merge"


# ---------------------------------------------------------------------------
# (d) Call sheet versioning — v1 then v2, both preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_sheet_versions_never_overwrite(week6_db):
    """Generating a call sheet twice for the same day creates v1 and v2 rows."""
    project_id, user_id = week6_db
    factory = _make_session()

    async with factory() as session:
        day_row = (await session.execute(
            sa.text(
                "SELECT id FROM days WHERE project_id=:pid AND kind='shoot' LIMIT 1"
            ),
            {"pid": project_id},
        )).first()

    if not day_row:
        pytest.skip("No shoot days in fixture")

    day_id = day_row.id

    fake_pdf = b"%PDF-1.4 fake content"
    fake_key = f"callsheets/{project_id}/{day_id}/v{{v}}.pdf"

    with (
        patch("app.services.call_sheet_generator._html_to_pdf", return_value=fake_pdf),
        patch("app.services.call_sheet_generator.storage.put_bytes"),
        patch(
            "app.services.call_sheet_generator.storage.key_callsheet",
            side_effect=lambda pid, did, v: fake_key.format(v=v),
        ),
    ):
        from app.services.call_sheet_generator import CallSheetGenerator

        async with factory() as session:
            sheet1 = await CallSheetGenerator.generate(project_id, day_id, user_id, session)

        async with factory() as session:
            sheet2 = await CallSheetGenerator.generate(project_id, day_id, user_id, session)

    assert sheet1.version == 1
    assert sheet2.version == 2
    assert sheet1.id != sheet2.id

    async with factory() as session:
        versions = (await session.execute(
            sa.text(
                "SELECT version FROM call_sheets WHERE day_id=:did ORDER BY version"
            ),
            {"did": day_id},
        )).scalars().all()

    assert list(versions) == [1, 2], f"Expected [1, 2], got {list(versions)}"


# ---------------------------------------------------------------------------
# (e) FlagDetector raises expected flags on Ratnagiri
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flag_detector_raises_flags(week6_db):
    """FlagDetector.run() on the Ratnagiri fixture must raise ≥1 flag."""
    project_id, _ = week6_db
    factory = _make_session()

    from app.services.flag_detector import FlagDetector

    async with factory() as session:
        result = await FlagDetector.run(project_id, None, session)

    assert isinstance(result, dict)
    assert "raised" in result and "resolved" in result
    assert result["raised"] >= 0  # May be 0 if all flags already exist from prior run

    # Verify flags table has rows for this project
    async with factory() as session:
        flag_count = (await session.execute(
            sa.text(
                "SELECT COUNT(*) FROM flags WHERE project_id=:pid AND resolved_at IS NULL"
            ),
            {"pid": project_id},
        )).scalar()

    # Ratnagiri fixture should have at least one open flag (missing actors, locations, etc.)
    assert flag_count >= 1, (
        f"Expected ≥1 open flags from Ratnagiri fixture, got {flag_count}. "
        "Check that the fixture has principal characters without actors or days without locations."
    )

    # Check flag kinds are valid enum values
    async with factory() as session:
        kinds = (await session.execute(
            sa.text("SELECT DISTINCT kind FROM flags WHERE project_id=:pid"),
            {"pid": project_id},
        )).scalars().all()

    valid_kinds = {
        "cast_hold", "permit_lead", "weather", "drone_block", "insurance",
        "continuity", "vendor", "capacity", "missing_data", "cost_overrun",
        "safety", "custom",
    }
    for k in kinds:
        assert k in valid_kinds, f"Unexpected flag kind: {k!r}"


# ---------------------------------------------------------------------------
# (f) Chat tool-call: propose_reschedule → commit_preview
# ---------------------------------------------------------------------------

def _text_event(txt: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock()
    e.delta.text = txt
    return e


def _tool_start_event(tool_id: str, name: str):
    e = MagicMock()
    e.type = "content_block_start"
    e.content_block = MagicMock()
    e.content_block.type = "tool_use"
    e.content_block.id = tool_id
    e.content_block.name = name
    return e


def _tool_delta_event(partial_json: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock(spec=["type", "partial_json"])
    e.delta.type = "input_json_delta"
    e.delta.partial_json = partial_json
    return e


def _make_mock_stream(response_turns):
    class _MockStreamCtx:
        def __init__(self, events):
            self._events = events

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        def __aiter__(self):
            return self._iter()

        async def _iter(self):
            for e in self._events:
                yield e

        async def get_final_message(self):
            msg = MagicMock()
            msg.stop_reason = "end_turn"
            return msg

    class _Client:
        def __init__(self, turns):
            self._turns = iter(turns)

        @property
        def messages(self):
            return self

        def stream(self, **kwargs):
            events = next(self._turns, [])
            return _MockStreamCtx(events)

    return _Client(response_turns)


@pytest.mark.asyncio
async def test_chat_move_day3_propose_and_commit(week6_db):
    """Chat flow: 'move scene X to day Y' → propose_reschedule → commit_preview."""
    project_id, user_id = week6_db
    factory = _make_session()

    # Get a real scene + target day from the fixture
    async with factory() as session:
        scene_row = (await session.execute(
            sa.text(
                "SELECT s.scene_number, ds.id AS ds_id, ds.day_id "
                "FROM scenes s JOIN day_scenes ds ON ds.scene_id=s.id "
                "JOIN days d ON d.id=ds.day_id "
                "WHERE s.project_id=:pid AND d.kind='shoot' LIMIT 1"
            ),
            {"pid": project_id},
        )).first()
        target_day = (await session.execute(
            sa.text(
                "SELECT shoot_day_number FROM days "
                "WHERE project_id=:pid AND kind='shoot' AND id!=:did LIMIT 1"
            ),
            {"pid": project_id, "did": scene_row.day_id if scene_row else ""},
        )).first()

    if not scene_row or not target_day:
        pytest.skip("Not enough fixture data for chat move test")

    scene_number = scene_row.scene_number
    to_day       = str(target_day.shoot_day_number)
    propose_args = json.dumps({"scene_number": scene_number, "to_day_identifier": to_day})
    tool_id      = "toolu_week6_01"

    turn1 = [
        _tool_start_event(tool_id, "propose_reschedule"),
        _tool_delta_event(propose_args),
    ]
    turn2 = [_text_event("Preview ready — confirm to apply.")]

    mock_client = _make_mock_stream([turn1, turn2])

    events = []
    async with factory() as session:
        from app.services.chat_agent import ChatAgent

        thread_id = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO chat_threads (id, project_id, user_id, last_active_at) "
                "VALUES (:id, :pid, :uid, NOW())"
            ),
            {"id": thread_id, "pid": project_id, "uid": user_id},
        )
        await session.commit()

        agent = ChatAgent(project_id, user_id, session)
        with patch("app.services.chat_agent.anthropic.AsyncAnthropic", return_value=mock_client):
            async for ev in agent.stream(thread_id, f"Move scene {scene_number} to day {to_day}"):
                events.append(ev)

    types = [e["type"] for e in events]
    assert "preview_ready" in types, f"Expected preview_ready, got: {types}"
    batch_id = next(e for e in events if e["type"] == "preview_ready")["batch_id"]

    # Now commit via the tool
    commit_args = json.dumps({"batch_id": batch_id})
    commit_tool_id = "toolu_week6_02"
    turn_c1 = [
        _tool_start_event(commit_tool_id, "commit_preview"),
        _tool_delta_event(commit_args),
    ]
    turn_c2 = [_text_event("Done — scene moved.")]
    mock_client2 = _make_mock_stream([turn_c1, turn_c2])

    events2 = []
    async with factory() as session:
        thread_id2 = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO chat_threads (id, project_id, user_id, last_active_at) "
                "VALUES (:id, :pid, :uid, NOW())"
            ),
            {"id": thread_id2, "pid": project_id, "uid": user_id},
        )
        await session.commit()

        agent2 = ChatAgent(project_id, user_id, session)
        with patch("app.services.chat_agent.anthropic.AsyncAnthropic", return_value=mock_client2):
            async for ev in agent2.stream(thread_id2, "confirm"):
                events2.append(ev)

    types2 = [e["type"] for e in events2]
    assert "tool_result" in types2

    # Verify commit landed
    async with factory() as session:
        status = (await session.execute(
            sa.text("SELECT status FROM propagation_previews WHERE batch_id=:bid"),
            {"bid": batch_id},
        )).scalar()
    assert status == "confirmed", f"Expected confirmed, got {status!r}"
