"""Project CRUD routes — v1 schema (no parsed_json)."""
from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import Project, User
from ..parser_service import parse_xlsx_bytes
from ..services import project_ingestor

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProjectSummary(BaseModel):
    id: str
    title: str
    window: str | None = None
    status: str
    shoot_days: int
    total_days: int
    created_at: str
    updated_at: str


class ProjectDetail(BaseModel):
    id: str
    title: str
    window: str | None = None
    status: str
    start_date: date | None = None
    end_date: date | None = None
    live_scenario_id: str | None = None
    shoot_days: int
    total_days: int
    unit_cols: list[str]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_project_or_404(
    project_id: str,
    user: User,
    session: AsyncSession,
) -> Project:
    result = await session.execute(
        sa.select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> list[ProjectSummary]:
    rows = (await session.execute(
        sa.text("""
            SELECT
                p.id, p.title, p."window", p.status,
                p.created_at, p.updated_at,
                COALESCE(SUM(CASE WHEN d.kind = 'shoot' THEN 1 ELSE 0 END), 0) AS shoot_days,
                COUNT(d.id) AS total_days
            FROM projects p
            LEFT JOIN days d ON d.project_id = p.id
            WHERE p.owner_id = :uid
            GROUP BY p.id
            ORDER BY p.updated_at DESC
        """),
        {"uid": user.id},
    )).fetchall()

    return [
        ProjectSummary(
            id=r.id,
            title=r.title,
            window=r.window,
            status=r.status,
            shoot_days=int(r.shoot_days),
            total_days=int(r.total_days),
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@router.post("", response_model=ProjectDetail, status_code=201)
async def create_project(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> ProjectDetail:
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Upload an .xlsx file.")

    data = await file.read()
    try:
        parsed = parse_xlsx_bytes(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse master: {exc}")

    project_id = str(uuid.uuid4())
    await session.execute(
        sa.text(
            "INSERT INTO projects "
            "(id, owner_id, title, \"window\", source_file, source_filename, status, created_at, updated_at) "
            "VALUES (:id, :uid, :title, :window, :src, :fname, 'pre', NOW(), NOW())"
        ),
        {
            "id": project_id,
            "uid": user.id,
            "title": parsed["title"],
            "window": parsed.get("window"),
            "src": data,
            "fname": file.filename,
        },
    )

    await project_ingestor.ingest(project_id, user.id, parsed, session)

    # Reload for response
    p_row = (await session.execute(
        sa.text(
            "SELECT id, title, \"window\", status, start_date, end_date, "
            "live_scenario_id, created_at, updated_at FROM projects WHERE id = :pid"
        ),
        {"pid": project_id},
    )).first()

    unit_cols = [
        r.unit_code
        for r in (await session.execute(
            sa.text("SELECT unit_code FROM camera_units WHERE project_id = :pid ORDER BY unit_code"),
            {"pid": project_id},
        )).fetchall()
    ]
    counts = (await session.execute(
        sa.text("""
            SELECT
                COALESCE(SUM(CASE WHEN kind = 'shoot' THEN 1 ELSE 0 END), 0) AS shoot_days,
                COUNT(*) AS total_days
            FROM days WHERE project_id = :pid
        """),
        {"pid": project_id},
    )).first()

    return ProjectDetail(
        id=p_row.id,
        title=p_row.title,
        window=p_row.window,
        status=p_row.status,
        start_date=p_row.start_date,
        end_date=p_row.end_date,
        live_scenario_id=p_row.live_scenario_id,
        shoot_days=int(counts.shoot_days),
        total_days=int(counts.total_days),
        unit_cols=unit_cols,
        created_at=p_row.created_at.isoformat(),
        updated_at=p_row.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET ONE
# ---------------------------------------------------------------------------

@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> ProjectDetail:
    p_row = (await session.execute(
        sa.text(
            "SELECT p.id, p.title, p.\"window\", p.status, p.start_date, p.end_date, "
            "p.live_scenario_id, p.created_at, p.updated_at "
            "FROM projects p "
            "WHERE p.id = :pid AND p.owner_id = :uid"
        ),
        {"pid": project_id, "uid": user.id},
    )).first()
    if not p_row:
        raise HTTPException(status_code=404, detail="Project not found")

    unit_cols = [
        r.unit_code
        for r in (await session.execute(
            sa.text("SELECT unit_code FROM camera_units WHERE project_id = :pid ORDER BY unit_code"),
            {"pid": project_id},
        )).fetchall()
    ]
    counts = (await session.execute(
        sa.text("""
            SELECT
                COALESCE(SUM(CASE WHEN kind = 'shoot' THEN 1 ELSE 0 END), 0) AS shoot_days,
                COUNT(*) AS total_days
            FROM days WHERE project_id = :pid
        """),
        {"pid": project_id},
    )).first()

    return ProjectDetail(
        id=p_row.id,
        title=p_row.title,
        window=p_row.window,
        status=p_row.status,
        start_date=p_row.start_date,
        end_date=p_row.end_date,
        live_scenario_id=p_row.live_scenario_id,
        shoot_days=int(counts.shoot_days),
        total_days=int(counts.total_days),
        unit_cols=unit_cols,
        created_at=p_row.created_at.isoformat(),
        updated_at=p_row.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@router.delete("/{project_id}", status_code=204, response_class=Response)
async def delete_project(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    p = await _get_project_or_404(project_id, user, session)
    await session.delete(p)
    await session.commit()
