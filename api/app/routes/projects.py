"""Project CRUD routes — v1 schema (no parsed_json)."""
from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
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
    my_role: str | None = None  # super | producer | contributor
    start_date: date | None = None
    end_date: date | None = None
    live_scenario_id: str | None = None
    shoot_days: int
    total_days: int
    unit_cols: list[str]
    settings: dict = {}
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
            sa.or_(
                Project.owner_id == user.id,
                sa.literal(is_team_member(user)),
                sa.text("EXISTS (SELECT 1 FROM workspace_members wm "
                        "WHERE wm.project_id = projects.id AND wm.email = :uemail)"
                        ).bindparams(uemail=user.email.lower()),
            ),
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
            WHERE (p.owner_id = :uid OR :team = TRUE
                   OR EXISTS (SELECT 1 FROM workspace_members wm WHERE wm.project_id = p.id AND wm.email = :uemail))
            GROUP BY p.id
            ORDER BY p.updated_at DESC
        """),
        {"uid": user.id, "team": is_team_member(user), "uemail": user.email.lower()},
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
            "live_scenario_id, settings, created_at, updated_at FROM projects WHERE id = :pid"
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
        settings=p_row.settings or {},
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
            "p.live_scenario_id, p.settings, p.created_at, p.updated_at "
            "FROM projects p "
            "WHERE p.id = :pid AND (p.owner_id = :uid OR :team = TRUE "
            "OR EXISTS (SELECT 1 FROM workspace_members wm WHERE wm.project_id = p.id AND wm.email = :uemail))"
        ),
        {"pid": project_id, "uid": user.id, "team": is_team_member(user),
         "uemail": user.email.lower()},
    )).first()
    if not p_row:
        raise HTTPException(status_code=404, detail="Project not found")

    from ..auth import project_role
    my_role = await project_role(project_id, user, session)

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
        my_role=my_role,
        start_date=p_row.start_date,
        end_date=p_row.end_date,
        live_scenario_id=p_row.live_scenario_id,
        shoot_days=int(counts.shoot_days),
        total_days=int(counts.total_days),
        unit_cols=unit_cols,
        settings=p_row.settings or {},
        created_at=p_row.created_at.isoformat(),
        updated_at=p_row.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@router.delete("/{project_id}", status_code=204, response_class=Response, response_model=None)
async def delete_project(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
):
    p = await _get_project_or_404(project_id, user, session)
    await session.delete(p)
    await session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Editorial workspaces — create without a film master
# ---------------------------------------------------------------------------

class EditorialWorkspaceIn(BaseModel):
    title: str


@router.post("/editorial", status_code=201)
async def create_editorial_workspace(
    body: EditorialWorkspaceIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Give the workspace a name")
    project_id = str(uuid.uuid4())
    await session.execute(
        sa.text("INSERT INTO projects (id, owner_id, title, source_file, source_filename, "
                "status, settings, created_at, updated_at) "
                "VALUES (:id, :uid, :title, :src, 'editorial', 'pre', CAST(:st AS jsonb), NOW(), NOW())"),
        {"id": project_id, "uid": user.id, "title": title, "src": b"",
         "st": '{"mode": "editorial"}'},
    )
    await session.commit()
    return {"id": project_id, "title": title}




async def _assert_workspace_access(
    project_id: str, user: User, session: AsyncSession, min_role: str = "contributor",
) -> None:
    from ..auth import project_role

    role = await project_role(project_id, user, session)
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if min_role == "producer" and role == "contributor":
        raise HTTPException(status_code=403, detail="Producers only")

# ---------------------------------------------------------------------------
# Workspace members — app-managed team access
# ---------------------------------------------------------------------------

class MemberIn(BaseModel):
    email: str
    name: str | None = None
    role: str = "contributor"  # producer | contributor


def _member_out(r) -> dict:
    return {"id": r.id, "email": r.email, "name": r.name, "role": r.role,
            "added_by": r.added_by, "created_at": r.created_at.isoformat()}




async def _send_welcome_email(email: str, name: str | None, role: str,
                              workspace: str, added_by: str) -> None:
    """Branded invitation: you're in, here's where to sign in."""
    from ..services import emailer

    nice_name = (name.strip()[:1].upper() + name.strip()[1:]) if name else None
    greeting = f"Hi {nice_name}," if nice_name else "Hi,"
    role_line = ("You&rsquo;ll see each shoot day as it takes shape: the briefs, the "
                 "call times, your own private notes, and, if you want it, every day "
                 "placed neatly in your Google Calendar."
                 if role == "contributor" else
                 "As a producer, the room is yours: the calendar, the day briefs, "
                 "the expenses and the team.")
    body = (
        f"<p style='margin:14px 0 10px'>{greeting}</p>"
        f"<p style='margin:0 0 4px'>{added_by} has added you to "
        f"<strong>{workspace}</strong>. Which means the calendar, the call times and "
        f"the quiet machinery of the shoot now live one sign-in away.</p>"
        + emailer.kv_rows([
            ("Workspace", workspace),
            ("Your role", "Producer" if role == "producer" else "Contributor"),
            ("Added by", added_by),
        ])
        + f"<p style='margin:16px 0 0;font-size:14.5px;line-height:1.7'>{role_line}</p>"
        + emailer.button("Sign in to Cue", f"{emailer._base()}/login")
        + f"<p style='margin:22px 0 0;font-size:12.5px;color:{emailer.MUTED};line-height:1.7'>"
        f"Sign in with this address. Google is fastest; an emailed link works just "
        f"as well. We&rsquo;ll see you on set.</p>"
    )
    html = emailer.frame(
        eyebrow="CUE · WORKSPACE INVITATION",
        headline="Welcome to the production.",
        sub=None,
        body_html=body,
    )
    await emailer.send(email, f"Welcome to {workspace}", html)


@router.get("/{project_id}/members")
async def list_members(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _assert_workspace_access(project_id, user, session, min_role="producer")
    rows = (await session.execute(
        sa.text("SELECT id, email, name, role, added_by, created_at FROM workspace_members "
                "WHERE project_id = :pid ORDER BY created_at"),
        {"pid": project_id},
    )).fetchall()
    from ..auth import is_super_admin
    from ..config import settings as _settings
    members = [{**_member_out(r), "builtin": False}
               for r in rows if not is_super_admin(r.email)]
    listed = {m["email"] for m in members}
    # Core producers from the environment allowlist belong on this page too —
    # they just can't be removed from here.
    for em in (e.strip().lower() for e in _settings.allowed_emails.split(",") if e.strip()):
        if em in listed or is_super_admin(em):
            continue
        pretty = " ".join(w.capitalize() for w in em.split("@")[0].replace(".", " ").split())
        members.append({"id": f"env:{em}", "email": em, "name": pretty,
                        "role": "producer", "added_by": None,
                        "created_at": "", "builtin": True})
    return {"members": members}


@router.post("/{project_id}/members")
async def add_member(
    project_id: str,
    body: MemberIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    from ..services import activity

    await _assert_workspace_access(project_id, user, session, min_role="producer")
    email = body.email.lower().strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="That doesn't look like an email address")
    from ..auth import is_super_admin
    if is_super_admin(email):
        raise HTTPException(status_code=409, detail="That account already has full access")
    if body.role not in ("producer", "contributor"):
        raise HTTPException(status_code=422, detail="Role must be producer or contributor")
    existing = (await session.execute(
        sa.text("SELECT id FROM workspace_members WHERE project_id = :pid AND email = :em"),
        {"pid": project_id, "em": email},
    )).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already a member of this workspace")
    member_id = str(uuid.uuid4())
    await session.execute(
        sa.text("INSERT INTO workspace_members (id, project_id, email, name, role, added_by, created_at) "
                "VALUES (:id, :pid, :em, :nm, :rl, :by, NOW())"),
        {"id": member_id, "pid": project_id, "em": email,
         "nm": body.name or None, "rl": body.role, "by": user.email},
    )
    await activity.log(session, project_id, user, "member.added",
                       f"Added {body.name or email} to the workspace as {body.role}")
    proj_title = (await session.execute(
        sa.text("SELECT title FROM projects WHERE id = :pid"), {"pid": project_id},
    )).scalar()
    await session.commit()
    try:
        await _send_welcome_email(email, body.name, body.role, proj_title or "a Cue workspace",
                                  user.name or user.email)
    except Exception:
        pass  # membership stands even if the mail bounces
    row = (await session.execute(
        sa.text("SELECT id, email, name, role, added_by, created_at FROM workspace_members WHERE id = :id"),
        {"id": member_id},
    )).first()
    return _member_out(row)


@router.delete("/{project_id}/members/{member_id}", status_code=204,
               response_class=Response, response_model=None)
async def remove_member(
    project_id: str,
    member_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    from ..services import activity

    await _assert_workspace_access(project_id, user, session, min_role="producer")
    row = (await session.execute(
        sa.text("SELECT id, email, name FROM workspace_members "
                "WHERE id = :id AND project_id = :pid"),
        {"id": member_id, "pid": project_id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")
    await session.execute(sa.text("DELETE FROM workspace_members WHERE id = :id"), {"id": row.id})
    await activity.log(session, project_id, user, "member.removed",
                       f"Removed {row.name or row.email} from the workspace")
    await session.commit()
