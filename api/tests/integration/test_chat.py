"""Integration tests for the chat agent tool-call flow.

Uses a mocked Anthropic client so no real API calls are made.
Tests the full tool-call → tool-result → commit_preview pipeline
against the Ratnagiri DB fixture.

Run with:
    DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
    pytest tests/integration/test_chat.py -v -s
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, AsyncIterator
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

API_DIR      = Path(__file__).parents[2]
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_XLSX  = FIXTURES_DIR / "ratnagiri_master.xlsx"
ALEMBIC_INI  = API_DIR / "alembic.ini"

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://cue:cue@localhost:5432/cue",
).replace("+asyncpg", "+psycopg2")

ASYNC_DB_URL = DB_URL.replace("+psycopg2", "+asyncpg")

# ---------------------------------------------------------------------------
# Module-scoped DB fixture (shared with snapshot tests if run in same session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def chat_db():
    """Wipe schema → migrate → ingest Ratnagiri → return (project_id, user_id)."""
    import json as _json
    from sqlalchemy import text

    sync_engine = create_engine(DB_URL, future=True)

    # Wipe and migrate
    with sync_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    alembic_cmd.upgrade(cfg, "head")

    # Insert a user
    user_id = str(uuid.uuid4())
    with sync_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
            {"id": user_id, "email": "test@cue.app", "name": "Test"},
        )
        conn.commit()

    # Parse and ingest the sample xlsx
    from app.parser_service import parse_xlsx_bytes
    from app.services import project_ingestor

    data = SAMPLE_XLSX.read_bytes()
    parsed = parse_xlsx_bytes(data)

    project_id = str(uuid.uuid4())
    with sync_engine.connect() as conn:
        conn.execute(
            text(
                'INSERT INTO projects (id, owner_id, title, "window", source_file, source_filename, status) '
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


# ---------------------------------------------------------------------------
# Async session factory for tests
# ---------------------------------------------------------------------------

def _make_session(db_url: str):
    engine = create_async_engine(db_url)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Mock Anthropic streaming
# ---------------------------------------------------------------------------

def _make_mock_stream(response_turns: list[list[dict]]):
    """
    Build a mock async context manager whose `.stream()` produces a sequence
    of event lists, one list per model turn.

    Each event dict must have a "type" key matching the Anthropic stream event types.
    """

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


def _text_event(text: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock()
    e.delta.text = text
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
    # not a text delta
    del e.delta.text  # remove text attribute to avoid confusion
    e.delta = MagicMock(spec=["type", "partial_json"])
    e.delta.type = "input_json_delta"
    e.delta.partial_json = partial_json
    return e


# ---------------------------------------------------------------------------
# Test: tool-call flow (get_project_overview)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_overview_tool(chat_db):
    project_id, user_id = chat_db

    factory = _make_session(ASYNC_DB_URL)

    # Mock Anthropic: first turn calls get_project_overview, second turn gives text reply
    tool_id = "toolu_001"

    turn1 = [
        _tool_start_event(tool_id, "get_project_overview"),
        _tool_delta_event("{}"),
    ]
    turn2 = [
        _text_event("The project has "),
        _text_event("multiple shoot days."),
    ]

    mock_client = _make_mock_stream([turn1, turn2])

    events = []
    async with factory() as session:
        from app.services.chat_agent import ChatAgent

        # Create a thread first
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
            async for event in agent.stream(thread_id, "Give me a project overview"):
                events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "assistant_delta" in types
    assert "done" in types

    # tool_call event carries the right name
    tc_events = [e for e in events if e["type"] == "tool_call"]
    assert tc_events[0]["name"] == "get_project_overview"

    # tool_result carries project data
    tr_events = [e for e in events if e["type"] == "tool_result"]
    result = tr_events[0]["result"]
    assert "title" in result
    assert "shoot_days_total" in result


# ---------------------------------------------------------------------------
# Test: propose_reschedule → preview_ready event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_propose_reschedule_emits_preview_ready(chat_db):
    project_id, user_id = chat_db
    factory = _make_session(ASYNC_DB_URL)

    async with factory() as session:
        # Get a real scene_number and a target day
        scene_row = (await session.execute(
            sa.text(
                "SELECT s.scene_number, ds.day_id "
                "FROM scenes s JOIN day_scenes ds ON ds.scene_id=s.id "
                "JOIN days d ON d.id=ds.day_id "
                "WHERE s.project_id=:pid AND d.kind='shoot' "
                "LIMIT 1"
            ),
            {"pid": project_id},
        )).first()
        target_day = (await session.execute(
            sa.text(
                "SELECT d.shoot_day_number FROM days d "
                "WHERE d.project_id=:pid AND d.kind='shoot' "
                "AND d.id != :current_did "
                "LIMIT 1"
            ),
            {"pid": project_id, "current_did": scene_row.day_id},
        )).first()

    if not scene_row or not target_day:
        pytest.skip("Not enough data in fixture for reschedule test")

    scene_number = scene_row.scene_number
    to_day = str(target_day.shoot_day_number)
    propose_args = json.dumps({"scene_number": scene_number, "to_day_identifier": to_day})

    tool_id = "toolu_propose_01"
    turn1 = [
        _tool_start_event(tool_id, "propose_reschedule"),
        _tool_delta_event(propose_args),
    ]
    turn2 = [_text_event("Here is the preview.")]

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
            async for event in agent.stream(thread_id, f"Move scene {scene_number} to day {to_day}"):
                events.append(event)

    types = [e["type"] for e in events]
    assert "preview_ready" in types, f"Expected preview_ready, got: {types}"

    preview_events = [e for e in events if e["type"] == "preview_ready"]
    assert "batch_id" in preview_events[0]


# ---------------------------------------------------------------------------
# Test: commit_preview via tool call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_preview_tool(chat_db):
    project_id, user_id = chat_db
    factory = _make_session(ASYNC_DB_URL)

    # First, create a real preview via propose_reschedule
    async with factory() as session:
        scene_row = (await session.execute(
            sa.text(
                "SELECT s.id AS scene_id, s.scene_number, ds.id AS ds_id, ds.day_id "
                "FROM scenes s JOIN day_scenes ds ON ds.scene_id=s.id "
                "JOIN days d ON d.id=ds.day_id "
                "WHERE s.project_id=:pid AND d.kind='shoot' LIMIT 1"
            ),
            {"pid": project_id},
        )).first()
        target_day_row = (await session.execute(
            sa.text(
                "SELECT id FROM days WHERE project_id=:pid AND kind='shoot' AND id!=:did LIMIT 1"
            ),
            {"pid": project_id, "current_did": scene_row.day_id if scene_row else ""},
        )).first()

    if not scene_row or not target_day_row:
        pytest.skip("Not enough fixture data")

    from app.services.propagation_engine import PropagationEngine

    async with factory() as session:
        preview = await PropagationEngine.preview(
            project_id=project_id,
            user_id=user_id,
            raw_edits=[{
                "op": "patch",
                "entity": "day_scenes",
                "id": scene_row.ds_id,
                "fields": {"day_id": target_day_row.id, "order_in_day": 1},
            }],
            session=session,
        )
        batch_id = preview.batch_id

    commit_args = json.dumps({"batch_id": batch_id})
    tool_id = "toolu_commit_01"
    turn1 = [
        _tool_start_event(tool_id, "commit_preview"),
        _tool_delta_event(commit_args),
    ]
    turn2 = [_text_event("Changes committed successfully.")]

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
            async for event in agent.stream(thread_id, "confirm"):
                events.append(event)

    # Verify the commit happened
    async with factory() as session:
        committed = (await session.execute(
            sa.text("SELECT status FROM propagation_previews WHERE batch_id=:bid"),
            {"bid": batch_id},
        )).scalar()
    assert committed == "confirmed"

    types = [e["type"] for e in events]
    assert "tool_result" in types
    commit_results = [e for e in events if e["type"] == "tool_result" and e["name"] == "commit_preview"]
    assert commit_results[0]["result"].get("ok") is True
