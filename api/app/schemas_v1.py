"""v1 response schemas.

These back the ``response_model=`` on routes that previously returned bare
dicts. They exist so ``openapi-typescript`` can generate real types for the
frontend.

All view-response envelopes use ``extra='allow'`` so renderer changes don't
drop fields — the schema documents the known shape, not the ceiling.
"""
from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared view envelope
# ---------------------------------------------------------------------------

class _ViewEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    view: str
    project_id: str
    scenario_id: str | None = None
    computed_at: str


# ---------------------------------------------------------------------------
# Main schedule
# ---------------------------------------------------------------------------

class ScheduleLocation(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    area: str | None = None
    kind: str | None = None


class ScheduleScene(BaseModel):
    model_config = ConfigDict(extra="allow")

    scene_id: str
    scene_number: str
    title: str | None = None
    dn: str | None = None
    page_eighths: float | None = None
    setups_est: int | None = None
    order_in_day: int | None = None


class ScheduleCameraUnit(BaseModel):
    model_config = ConfigDict(extra="allow")

    unit_code: str
    kind: str
    count: int


class ScheduleDay(BaseModel):
    model_config = ConfigDict(extra="allow")

    day_id: str
    date: str
    day_of_week: str
    shoot_day_number: int | None = None
    kind: str
    location: ScheduleLocation | None = None
    scenes: list[ScheduleScene] = []
    cast: list[str] = []
    camera_units: list[ScheduleCameraUnit] = []
    jr_count: int | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    notes: str | None = None


class ScheduleMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_days: int
    shoot_days: int
    start_date: str | None = None
    end_date: str | None = None


class MainScheduleResponse(_ViewEnvelope):
    days: list[ScheduleDay]
    meta: ScheduleMeta


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

class CalendarSceneStrip(BaseModel):
    model_config = ConfigDict(extra="allow")

    scene_number: str
    title: str | None = None
    dn: str | None = None


class CalendarDay(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    day_of_week: str
    kind: str | None = None
    shoot_day_number: int | None = None
    location: str | None = None
    scenes: list[CalendarSceneStrip] = []
    scene_count: int = 0
    page_eighths_total: float | None = None
    setups_total: int | None = None
    jr_count: int | None = None
    shift_start: str | None = None
    shift_end: str | None = None
    banner_text: str | None = None


class CalendarMonth(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    year: int
    month: int
    days: list[CalendarDay]


class CalendarResponse(_ViewEnvelope):
    months: list[CalendarMonth]
    unscheduled: list[CalendarSceneStrip] = []


# ---------------------------------------------------------------------------
# Cast DOOD
# ---------------------------------------------------------------------------

class DoodShootDay(BaseModel):
    model_config = ConfigDict(extra="allow")

    day_id: str
    shoot_day_number: int
    date: str
    label: str


class DoodCharacter(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_id: str
    canonical_name: str
    display_name: str | None = None
    actor_name: str | None = None
    is_principal: bool = True
    days: dict[str, str] = {}


class CastDoodResponse(_ViewEnvelope):
    shoot_days: list[DoodShootDay]
    characters: list[DoodCharacter]
    day_totals: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Scenes matrix
# ---------------------------------------------------------------------------

class SceneMatrixScene(BaseModel):
    model_config = ConfigDict(extra="allow")

    scene_id: str
    scene_number: str
    title: str | None = None
    dn: str | None = None
    page_eighths: float | None = None
    characters: list[str] = []
    day_numbers: list[int] = []


class SceneMatrixMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_pages_eighths: float | None = None
    day_count: int
    night_count: int
    ext_count: int
    int_count: int


class ScenesMatrixResponse(_ViewEnvelope):
    shoot_days: list[DoodShootDay]
    scenes: list[SceneMatrixScene]
    meta: SceneMatrixMeta


# ---------------------------------------------------------------------------
# Edit DSL
# ---------------------------------------------------------------------------

class PreviewDiff(BaseModel):
    """Loosely-typed propagation diff envelope.

    The concrete shape depends on which entities were touched. We document the
    consistently-present fields and let the rest ride on ``extra='allow'``.
    """
    model_config = ConfigDict(extra="allow")

    views_affected: list[str] = []
    breaks: list[dict[str, Any]] = []
    side_effects: list[dict[str, Any]] = []
    flags_raised: list[dict[str, Any]] = []


class PropagationPreviewResponse(BaseModel):
    batch_id: str
    diff: PreviewDiff
    expires_at: str


class CommitEditsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = True
    views_regenerated: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Call sheets
# ---------------------------------------------------------------------------

class CallsheetSyncResult(BaseModel):
    call_sheet_id: str
    version: int
    pdf_s3_key: str | None = None
    status: str


class QueuedJobResult(BaseModel):
    queued: bool = True
    job_id: str | None = None


CallsheetGenerateResponse = Union[CallsheetSyncResult, QueuedJobResult]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

class ExportBundleResponse(BaseModel):
    job_id: str
    arq_job_id: str | None = None
