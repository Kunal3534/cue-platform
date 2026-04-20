"""ChatAgent — Anthropic SDK streaming with tool-use.

Streams ChatEvent dicts to the caller (route layer converts to SSE frames).

Event types:
  {"type": "assistant_delta", "text": "..."}
  {"type": "tool_call",   "name": "...", "arguments": {...}}
  {"type": "tool_result", "name": "...", "result": {...}}
  {"type": "preview_ready", "batch_id": "..."}
  {"type": "done"}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import ChatMessage, ChatThread
from .chat_prompts import SYSTEM_PROMPT
from .chat_tools import TOOLS, ToolExecutor


ChatEvent = dict[str, Any]


class ChatAgent:
    def __init__(
        self,
        project_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> None:
        self.project_id = project_id
        self.user_id = user_id
        self.session = session

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def stream(
        self,
        thread_id: str,
        user_message: str,
    ) -> AsyncIterator[ChatEvent]:
        """Yield ChatEvent dicts; caller serialises to SSE frames."""
        import anthropic

        # ── 1. Persist the user message ──────────────────────────────
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role="user",
            content=user_message,
        )
        self.session.add(user_msg)
        await self.session.flush()

        # ── 2. Load thread history for context window ─────────────────
        history = await self._load_history(thread_id)

        # ── 3. Build message list for Anthropic ───────────────────────
        messages: list[dict] = history + [{"role": "user", "content": user_message}]

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or "")
        executor = ToolExecutor(self.project_id, self.user_id, self.session)

        # ── 4. Agentic loop ───────────────────────────────────────────
        assistant_text_acc = ""
        tool_calls_acc: list[dict] = []
        edits_batch_id: str | None = None

        while True:
            # Collect the full streaming response for this turn
            turn_text = ""
            turn_tool_calls: list[dict] = []

            async with client.messages.stream(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                async for event in stream:
                    # Text delta
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            chunk = event.delta.text
                            turn_text += chunk
                            yield {"type": "assistant_delta", "text": chunk}

                    # Tool use block start — capture name + build args
                    elif event.type == "content_block_start":
                        if getattr(event.content_block, "type", None) == "tool_use":
                            turn_tool_calls.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input_raw": "",
                            })

                    elif event.type == "content_block_delta":
                        if (
                            hasattr(event.delta, "type")
                            and event.delta.type == "input_json_delta"
                            and turn_tool_calls
                        ):
                            turn_tool_calls[-1]["input_raw"] += event.delta.partial_json

                final_msg = await stream.get_final_message()

            stop_reason = final_msg.stop_reason

            # ── 5. If no tool calls, we're done ───────────────────────
            if not turn_tool_calls:
                assistant_text_acc += turn_text
                break

            # ── 6. Execute tools, emit events ─────────────────────────
            tool_results_for_api: list[dict] = []
            for tc in turn_tool_calls:
                try:
                    args = json.loads(tc["input_raw"]) if tc["input_raw"] else {}
                except json.JSONDecodeError:
                    args = {}

                yield {"type": "tool_call", "name": tc["name"], "arguments": args}

                result = await executor.execute(tc["name"], args)

                yield {"type": "tool_result", "name": tc["name"], "result": result}

                # Surface preview_ready when a propose_* tool returns a batch_id
                if isinstance(result, dict) and "batch_id" in result and "error" not in result:
                    edits_batch_id = result["batch_id"]
                    yield {"type": "preview_ready", "batch_id": edits_batch_id}

                tool_results_for_api.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result),
                })
                tool_calls_acc.append({"name": tc["name"], "arguments": args})

            # ── 7. Append assistant turn + tool results to message list ─
            assistant_content: list[dict] = []
            if turn_text:
                assistant_content.append({"type": "text", "text": turn_text})
            for tc in turn_tool_calls:
                try:
                    inp = json.loads(tc["input_raw"]) if tc["input_raw"] else {}
                except json.JSONDecodeError:
                    inp = {}
                assistant_content.append(
                    {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": inp}
                )

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results_for_api})

            if stop_reason == "end_turn":
                break

        # ── 8. Persist assistant message ──────────────────────────────
        asst_msg = ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role="assistant",
            content=assistant_text_acc or None,
            tool_calls=tool_calls_acc or None,
            edits_batch_id=edits_batch_id,
        )
        self.session.add(asst_msg)

        # Update thread last_active_at
        await self.session.execute(
            sa.text("UPDATE chat_threads SET last_active_at=NOW() WHERE id=:tid"),
            {"tid": thread_id},
        )
        await self.session.commit()

        yield {"type": "done"}

    # ------------------------------------------------------------------

    async def _load_history(self, thread_id: str) -> list[dict]:
        """Load recent messages for the context window (last 40 turns)."""
        rows = (await self.session.execute(
            sa.text(
                "SELECT role, content, tool_calls, tool_results "
                "FROM chat_messages WHERE thread_id=:tid "
                "ORDER BY created_at DESC LIMIT 40"
            ),
            {"tid": thread_id},
        )).fetchall()

        messages: list[dict] = []
        for r in reversed(rows):
            if r.role == "user":
                if r.content:
                    messages.append({"role": "user", "content": r.content})
            elif r.role == "assistant":
                content: list[dict] = []
                if r.content:
                    content.append({"type": "text", "text": r.content})
                if r.tool_calls:
                    for tc in r.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": str(uuid.uuid4()),
                            "name": tc.get("name", ""),
                            "input": tc.get("arguments", {}),
                        })
                if content:
                    messages.append({"role": "assistant", "content": content})
        return messages
