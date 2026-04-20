"""Redis pub/sub helpers for SSE project event streams.

publish(project_id, event) — called by commit hook, workers, etc.
subscribe(project_id)      — async generator yielding raw JSON strings for SSE.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..config import settings


def _channel(project_id: str) -> str:
    return f"project:{project_id}:events"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def publish(project_id: str, event: dict[str, Any]) -> None:
    """Fire-and-forget publish to Redis. Swallows errors if Redis is unavailable."""
    import redis.asyncio as aioredis
    try:
        r = await aioredis.from_url(settings.redis_url, decode_responses=True)
        payload = json.dumps({**event, "project_id": project_id, "ts": _now_iso()})
        await r.publish(_channel(project_id), payload)
        await r.aclose()
    except Exception:
        pass  # Redis unavailable — SSE not critical path


async def subscribe(project_id: str) -> AsyncIterator[str]:
    """Async generator; yields SSE-formatted data strings until the client disconnects."""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(project_id))
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe(_channel(project_id))
        await r.aclose()
