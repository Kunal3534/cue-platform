"""SSE event schema — TypedDicts shared across services and routes.

All events have:
  kind: str  — discriminator
  project_id: str
  ts: str    — ISO timestamp
"""
from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict


class BaseEvent(TypedDict):
    kind: str
    project_id: str
    ts: str


class SceneRescheduledEvent(BaseEvent):
    scene_id: str
    scene_number: str
    from_day_id: str | None
    to_day_id: str
    batch_id: str


class DayUpdatedEvent(BaseEvent):
    day_id: str
    shoot_day_number: int | None
    fields_changed: list[str]
    batch_id: str


class FlagRaisedEvent(BaseEvent):
    flag_id: str
    flag_kind: str
    severity: str
    title: str


class FlagResolvedEvent(BaseEvent):
    flag_id: str


class CallSheetRegeneratedEvent(BaseEvent):
    day_id: str
    call_sheet_id: str
    version: int


class CallSheetSentEvent(BaseEvent):
    day_id: str
    call_sheet_id: str
    version: int
    recipient_count: int


class ScenarioForkedEvent(BaseEvent):
    scenario_id: str
    scenario_name: str


class ScenarioMergedEvent(BaseEvent):
    scenario_id: str


class ChatMessageEvent(BaseEvent):
    thread_id: str
    message_id: str
    role: str
    content_preview: str  # first 120 chars


# Convenience: union type for type checkers
AnyEvent = (
    SceneRescheduledEvent
    | DayUpdatedEvent
    | FlagRaisedEvent
    | FlagResolvedEvent
    | CallSheetRegeneratedEvent
    | CallSheetSentEvent
    | ScenarioForkedEvent
    | ScenarioMergedEvent
    | ChatMessageEvent
)
