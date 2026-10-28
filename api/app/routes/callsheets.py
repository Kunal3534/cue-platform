"""Call sheet routes.

GET  /projects/{project_id}/callsheets
     List all call sheets for the project (latest version per day).

POST /projects/{project_id}/days/{day_id}/callsheets/generate
     Enqueue PDF generation for a shoot day (returns job stub).
     Sync path also available as a query param: ?sync=true

GET  /projects/{project_id}/callsheets/{call_sheet_id}/pdf
     Redirect to pre-signed S3 URL for the PDF.

POST /projects/{project_id}/callsheets/{call_sheet_id}/send
     Enqueue email send to unit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import User, CallSheet
from ..schemas_v1 import (
    CallsheetGenerateResponse,
    CallsheetSyncResult,
    QueuedJobResult,
)
from ..services import storage
from ..services.call_sheet_generator import CallSheetGenerator

router = APIRouter(prefix="/projects", tags=["callsheets"])


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------

class CallSheetSummary(BaseModel):
    id: str
    day_id: str
    version: int
    status: str
    pdf_s3_key: str | None
    generated_at: str
    sent_at: str | None


class SendRequest(BaseModel):
    recipients: list[dict]  # [{name, email}]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_project_access(project_id: str, user: User, session: AsyncSession) -> None:
    row = (await session.execute(
        sa.text("SELECT id FROM projects WHERE id = :pid AND (owner_id = :uid OR :team = TRUE)"),
        {"pid": project_id, "uid": user.id, "team": is_team_member(user)},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@router.get("/{project_id}/callsheets", response_model=list[CallSheetSummary])
async def list_callsheets(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[CallSheetSummary]:
    await _assert_project_access(project_id, user, session)

    rows = (await session.execute(
        sa.text("""
            SELECT DISTINCT ON (day_id)
                id, day_id, version, status, pdf_s3_key, generated_at, sent_at
            FROM call_sheets
            WHERE project_id = :pid
            ORDER BY day_id, version DESC
        """),
        {"pid": project_id},
    )).fetchall()

    return [
        CallSheetSummary(
            id=r.id, day_id=r.day_id, version=r.version,
            status=r.status,
            pdf_s3_key=r.pdf_s3_key,
            generated_at=r.generated_at.isoformat(),
            sent_at=r.sent_at.isoformat() if r.sent_at else None,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GENERATE (sync or async)
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/days/{day_id}/callsheets/generate",
    response_model=CallsheetGenerateResponse,
)
async def generate_callsheet(
    project_id: str,
    day_id: str,
    sync: bool = Query(False, description="If true, generate synchronously and return the result"),
    scenario_id: str | None = Query(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _assert_project_access(project_id, user, session)

    # Verify the day belongs to this project
    day_row = (await session.execute(
        sa.text("SELECT id, kind FROM days WHERE id = :did AND project_id = :pid"),
        {"did": day_id, "pid": project_id},
    )).first()
    if not day_row:
        raise HTTPException(status_code=404, detail="Day not found")
    if day_row.kind not in ("shoot", "prep"):
        raise HTTPException(status_code=422, detail="Call sheets can only be generated for shoot or prep days")

    if sync:
        sheet = await CallSheetGenerator.generate(project_id, day_id, user.id, session, scenario_id)
        return {
            "call_sheet_id": sheet.id,
            "version": sheet.version,
            "pdf_s3_key": sheet.pdf_s3_key,
            "status": sheet.status,
        }
    else:
        # Enqueue via arq
        from arq import create_pool
        from ..worker import get_redis_settings
        pool = await create_pool(get_redis_settings())
        job = await pool.enqueue_job(
            "regenerate_call_sheet",
            project_id, day_id, user.id, scenario_id,
        )
        await pool.close()
        return {"queued": True, "job_id": job.job_id if job else None}


# ---------------------------------------------------------------------------
# PDF redirect
# ---------------------------------------------------------------------------

@router.get("/{project_id}/callsheets/{call_sheet_id}/pdf")
async def get_callsheet_pdf(
    project_id: str,
    call_sheet_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> RedirectResponse:
    await _assert_project_access(project_id, user, session)

    sheet = (await session.execute(
        sa.select(CallSheet).where(
            CallSheet.id == call_sheet_id,
            CallSheet.project_id == project_id,
        )
    )).scalar_one_or_none()

    if not sheet:
        raise HTTPException(status_code=404, detail="Call sheet not found")
    if not sheet.pdf_s3_key:
        raise HTTPException(status_code=404, detail="PDF not yet generated")

    url = storage.presigned_url(sheet.pdf_s3_key, expires_seconds=3600)
    return RedirectResponse(url=url, status_code=302)


# ---------------------------------------------------------------------------
# SEND
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/callsheets/{call_sheet_id}/send",
    response_model=QueuedJobResult,
)
async def send_callsheet(
    project_id: str,
    call_sheet_id: str,
    body: SendRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _assert_project_access(project_id, user, session)

    sheet = (await session.execute(
        sa.select(CallSheet).where(
            CallSheet.id == call_sheet_id,
            CallSheet.project_id == project_id,
        )
    )).scalar_one_or_none()

    if not sheet:
        raise HTTPException(status_code=404, detail="Call sheet not found")

    from arq import create_pool
    from ..worker import get_redis_settings
    pool = await create_pool(get_redis_settings())
    job = await pool.enqueue_job("send_call_sheet", call_sheet_id, body.recipients)
    await pool.close()
    return {"queued": True, "job_id": job.job_id if job else None}
