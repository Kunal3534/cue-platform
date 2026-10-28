"""Editorial (magazine-shoot) schedule — read + full CRUD for the simple UI.

Roles are deliberately coarse for now: the project owner (producer) can edit
through these authenticated routes; everyone else only ever sees the
read-only /share/{token} views. Todos are producer-only and are never
included in any share payload.

GET    /projects/{id}/editorial/schedule            — all shoot days, flat
PUT    /projects/{id}/editorial/days/{date}         — create/replace a shoot day
DELETE /projects/{id}/editorial/days/{date}         — remove a shoot day
POST   /projects/{id}/editorial/days/{date}/moodboard  — upload moodboard PDF
GET    /projects/{id}/editorial/days/{date}/moodboard  — redirect to the PDF
GET    /projects/{id}/todos                         — producer to-do list
PUT    /projects/{id}/todos                         — replace the to-do list
"""
from __future__ import annotations

import json
import uuid
from datetime import date as date_cls, time

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user, is_team_member
from ..db import get_async_db
from ..models import User
from ..services import activity, storage

router = APIRouter(prefix="/projects", tags=["editorial"])

MOODBOARD_MAX_BYTES = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

class TalentIn(BaseModel):
    name: str
    role: str | None = None
    call_time: str | None = None  # this talent's own call, "HH:MM"
    hmu_call: str | None = None  # legacy name for call_time — older clients still send it
    hmu_lead: str | None = None  # HMU artist for this talent

    @property
    def effective_call(self) -> str | None:
        return self.call_time or self.hmu_call


class ShootDayIn(BaseModel):
    talent: list[TalentIn] = []
    location_name: str | None = None
    location_area: str | None = None
    call_time: str | None = None
    wrap_time: str | None = None
    # Department calls shown in the day's call-times section
    lighting_call: str | None = None
    hmu_call: str | None = None
    crew_call: str | None = None
    photo_start: str | None = None
    film_start: str | None = None
    photographer: str | None = None
    video: str | None = None
    headline: str | None = None
    notes: str | None = None
    # None = leave the moodboard as-is; "" = clear it; a URL = external link
    moodboard_link: str | None = None


class MoveDayIn(BaseModel):
    to: str  # ISO date to move the shoot to


class TodoItem(BaseModel):
    id: str
    text: str
    done: bool = False
    date: str | None = None  # ISO date — todos are tied to a shoot day


class MarkerItem(BaseModel):
    """A decorated non-shoot event on the calendar: a festival holiday for
    everyone, or a personal day (birthday, leave) for one person."""
    id: str
    date: str  # ISO date
    label: str
    emoji: str = "🎉"
    kind: str = "holiday"  # "holiday" (everyone, shown on share) | "personal" (producers only)
    who: str | None = None  # for personal days: whose day it is


class MarkersIn(BaseModel):
    markers: list[MarkerItem]


class TodosIn(BaseModel):
    todos: list[TodoItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


def _t(hhmm: str | None) -> time | None:
    if not hhmm:
        return None
    try:
        h, m = hhmm.strip().split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"Bad time value: {hhmm!r} (use HH:MM)")


def _parse_date(raw: str) -> date_cls:
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Bad date: {raw!r} (use YYYY-MM-DD)")


async def _owner_project(project_id: str, user: User, session: AsyncSession):
    row = (await session.execute(
        sa.text("SELECT id, settings FROM projects WHERE id = :pid AND (owner_id = :uid OR :team = TRUE)"),
        {"pid": project_id, "uid": user.id, "team": is_team_member(user)},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return row


async def _clear_view_cache(project_id: str, session: AsyncSession) -> None:
    await session.execute(
        sa.text("DELETE FROM view_cache WHERE project_id = :pid"),
        {"pid": project_id},
    )


async def _renumber_shoot_days(project_id: str, session: AsyncSession) -> None:
    await session.execute(
        sa.text("UPDATE days SET shoot_day_number = NULL WHERE project_id = :pid AND kind <> 'shoot'"),
        {"pid": project_id},
    )
    await session.execute(
        sa.text("""
            WITH ranked AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY date) AS rn
                FROM days WHERE project_id = :pid AND kind = 'shoot'
            )
            UPDATE days d SET shoot_day_number = r.rn FROM ranked r WHERE d.id = r.id
        """),
        {"pid": project_id},
    )


def _moodboard_out(raw: dict | None) -> dict | None:
    if not raw:
        return None
    if raw.get("kind") == "link":
        return {"kind": "link", "url": raw.get("url")}
    if raw.get("kind") == "pdf":
        return {"kind": "pdf", "filename": raw.get("filename"), "pages": raw.get("pages", 0)}
    return None


def _rasterize_pdf(project_id: str, date_iso: str, data: bytes, max_pages: int = 12) -> int:
    """Render PDF pages to JPEGs in object storage so the briefing can show
    the moodboard inline in any browser. Returns the page count stored."""
    import io

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    n = min(len(doc), max_pages)
    for i in range(n):
        bitmap = doc[i].render(scale=1.7)
        buf = io.BytesIO()
        bitmap.to_pil().convert("RGB").save(buf, "JPEG", quality=85)
        storage.put_bytes(
            f"moodboards/{project_id}/{date_iso}/page-{i + 1}.jpg",
            buf.getvalue(),
            content_type="image/jpeg",
        )
    doc.close()
    return n


# ---------------------------------------------------------------------------
# Read — one payload drives calendar, schedule and day pages
# ---------------------------------------------------------------------------

async def build_schedule(project_id: str, session: AsyncSession) -> list[dict]:
    day_rows = (await session.execute(
        sa.text("""
            SELECT d.id, d.date, d.shoot_day_number, d.shift_start, d.shift_end,
                   d.banner_text, d.notes, d.crew, d.moodboard,
                   l.name AS loc_name, l.area AS loc_area
            FROM days d
            LEFT JOIN locations l ON l.id = d.primary_location_id
            WHERE d.project_id = :pid AND d.kind = 'shoot'
            ORDER BY d.date
        """),
        {"pid": project_id},
    )).fetchall()

    seg_rows = (await session.execute(
        sa.text("""
            SELECT ds.day_id, s.id AS scene_id, s.scene_number, s.title,
                   ds.estimated_start, ds.estimated_duration_minutes
            FROM day_scenes ds
            JOIN scenes s ON s.id = ds.scene_id
            JOIN days d ON d.id = ds.day_id
            WHERE d.project_id = :pid
            ORDER BY ds.day_id, ds.order_in_day
        """),
        {"pid": project_id},
    )).fetchall()

    talent_rows = (await session.execute(
        sa.text("""
            SELECT DISTINCT ds.day_id, c.id, c.display_name, c.notes AS role_label,
                   c.is_principal, c.actor_contact
            FROM day_scenes ds
            JOIN scene_characters sc ON sc.scene_id = ds.scene_id
            JOIN characters c ON c.id = sc.character_id
            JOIN days d ON d.id = ds.day_id
            WHERE d.project_id = :pid
            ORDER BY ds.day_id, c.is_principal DESC, c.display_name
        """),
        {"pid": project_id},
    )).fetchall()

    hmu_rows = (await session.execute(
        sa.text("""
            SELECT day_id, character_id, hmu_call_time, artist_lead
            FROM hmu_sessions WHERE project_id = :pid
        """),
        {"pid": project_id},
    )).fetchall()

    segs_by_day: dict[str, list[dict]] = {}
    for r in seg_rows:
        segs_by_day.setdefault(r.day_id, []).append({
            "ref": r.scene_number,
            "title": r.title,
            "start": r.estimated_start.strftime("%H:%M") if r.estimated_start else None,
            "duration_minutes": r.estimated_duration_minutes,
        })

    hmu_by_day_char = {(r.day_id, r.character_id): r for r in hmu_rows}

    talent_by_day: dict[str, list[dict]] = {}
    for r in talent_rows:
        h = hmu_by_day_char.get((r.day_id, r.id))
        call = h.hmu_call_time.strftime("%H:%M") if h and h.hmu_call_time else None
        talent_by_day.setdefault(r.day_id, []).append({
            "name": r.display_name,
            "role": r.role_label,
            "call_time": call,  # this talent's own call
            "hmu_call": call,  # legacy alias — older clients read this key
            "hmu_lead": h.artist_lead if h else None,
        })

    return [
        {
            "date": d.date.isoformat(),
            "day_of_week": d.date.strftime("%A"),
            "shoot_day_number": d.shoot_day_number,
            "headline": d.banner_text,
            "location": {"name": d.loc_name, "area": d.loc_area},
            "call_time": d.shift_start.strftime("%H:%M") if d.shift_start else None,
            "wrap_time": d.shift_end.strftime("%H:%M") if d.shift_end else None,
            "photographer": (d.crew or {}).get("photographer"),
            "video": (d.crew or {}).get("video"),
            "calls": (d.crew or {}).get("calls") or {},
            "talent": talent_by_day.get(d.id, []),
            "segments": segs_by_day.get(d.id, []),
            "notes": d.notes,
            "moodboard": _moodboard_out(d.moodboard),
        }
        for d in day_rows
    ]


@router.get("/{project_id}/editorial/schedule")
async def get_editorial_schedule(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    proj = await _owner_project(project_id, user, session)
    return {
        "days": await build_schedule(project_id, session),
        "markers": (proj.settings or {}).get("markers", []),
    }


# ---------------------------------------------------------------------------
# Write — upsert / delete a shoot day
# ---------------------------------------------------------------------------

@router.put("/{project_id}/editorial/days/{date}")
async def upsert_shoot_day(
    project_id: str,
    date: str,
    body: ShootDayIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    day_date = _parse_date(date)

    # Location: find-or-create by name
    loc_id = None
    if body.location_name and body.location_name.strip():
        name = body.location_name.strip()
        row = (await session.execute(
            sa.text("SELECT id FROM locations WHERE project_id = :pid AND name = :n"),
            {"pid": project_id, "n": name},
        )).first()
        if row:
            loc_id = row.id
            await session.execute(
                sa.text("UPDATE locations SET area = :a, updated_at = NOW() WHERE id = :id"),
                {"a": body.location_area, "id": loc_id},
            )
        else:
            loc_id = _uid()
            await session.execute(
                sa.text("INSERT INTO locations (id, project_id, name, area, kind, created_at, updated_at) "
                        "VALUES (:id, :pid, :n, :a, 'studio', NOW(), NOW())"),
                {"id": loc_id, "pid": project_id, "n": name, "a": body.location_area},
            )

    names = [t.name.strip() for t in body.talent if t.name.strip()]
    first_names = [n.split()[0] for n in names]
    headline = body.headline or (
        f"Shoot — {' · '.join(first_names)}" if first_names else "Shoot"
    )
    # Validate department calls up front (stored as strings in JSONB)
    for raw in (body.lighting_call, body.hmu_call, body.crew_call):
        _t(raw)
    crew = {
        "photographer": body.photographer or None,
        "video": body.video or None,
        "calls": {
            "lighting": (body.lighting_call or "").strip() or None,
            "hmu": (body.hmu_call or "").strip() or None,
            "crew": (body.crew_call or "").strip() or None,
        },
    }

    # Day: find-or-create by date, then promote to a shoot day
    day_row = (await session.execute(
        sa.text("SELECT id, kind, moodboard FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    was_shoot = bool(day_row and day_row.kind == "shoot")
    if day_row:
        day_id = day_row.id
    else:
        day_id = _uid()
        await session.execute(
            sa.text("INSERT INTO days (id, project_id, date, kind, created_at, updated_at) "
                    "VALUES (:id, :pid, :dt, 'shoot', NOW(), NOW())"),
            {"id": day_id, "pid": project_id, "dt": day_date},
        )

    # Moodboard: None keeps what's there, "" clears, a URL sets an external link
    moodboard_sql = ""
    moodboard_params: dict = {}
    if body.moodboard_link is not None:
        link = body.moodboard_link.strip()
        moodboard_sql = ", moodboard = CAST(:mb AS jsonb)"
        moodboard_params["mb"] = json.dumps({"kind": "link", "url": link}) if link else None

    await session.execute(
        sa.text(
            "UPDATE days SET kind = 'shoot', shift_start = :ss, shift_end = :se, "
            "primary_location_id = :loc, banner_text = :bn, crew = CAST(:cr AS jsonb), "
            f"notes = :nt, updated_at = NOW(){moodboard_sql} WHERE id = :id"
        ),
        {"ss": _t(body.call_time), "se": _t(body.wrap_time), "loc": loc_id,
         "bn": headline, "cr": json.dumps(crew), "nt": body.notes or None,
         "id": day_id, **moodboard_params},
    )

    # Talent: find-or-create characters by name, refresh role label
    char_ids: list[str] = []
    for t in body.talent:
        name = t.name.strip()
        if not name:
            continue
        cn = name.upper()
        row = (await session.execute(
            sa.text("SELECT id FROM characters WHERE project_id = :pid AND canonical_name = :cn"),
            {"pid": project_id, "cn": cn},
        )).first()
        if row:
            cid = row.id
            if t.role is not None:
                await session.execute(
                    sa.text("UPDATE characters SET notes = :nt, updated_at = NOW() WHERE id = :id"),
                    {"nt": t.role or None, "id": cid},
                )
        else:
            cid = _uid()
            await session.execute(
                sa.text("INSERT INTO characters (id, project_id, canonical_name, display_name, "
                        "is_principal, notes, created_at, updated_at) "
                        "VALUES (:id, :pid, :cn, :dn, FALSE, :nt, NOW(), NOW())"),
                {"id": cid, "pid": project_id, "cn": cn, "dn": name, "nt": t.role or None},
            )
        char_ids.append(cid)

    # Rebuild this day's segments from scratch (photos + film blocks)
    old_scenes = (await session.execute(
        sa.text("SELECT scene_id FROM day_scenes WHERE day_id = :did"), {"did": day_id},
    )).fetchall()
    for r in old_scenes:
        await session.execute(sa.text("DELETE FROM scenes WHERE id = :id"), {"id": r.scene_id})

    tag = day_date.strftime("%m%d")
    blocks = []
    if body.photo_start:
        blocks.append((f"P-{tag}", f"Photos — {' · '.join(first_names) or 'TBC'}", body.photo_start))
    if body.film_start:
        blocks.append((f"F-{tag}", f"Film — {' · '.join(first_names) or 'TBC'}", body.film_start))
    if not blocks and char_ids:
        # Talent is attached through segments, so a day without photo/film
        # times still needs one untimed block to carry its talent.
        blocks.append((f"S-{tag}", headline, None))
    for order, (ref, title, start) in enumerate(blocks, 1):
        scene_id = _uid()
        await session.execute(
            sa.text("INSERT INTO scenes (id, project_id, scene_number, title, dn, location_id, "
                    "sequence, status, created_at, updated_at) "
                    "VALUES (:id, :pid, :sn, :t, 'day_int', :loc, :seq, 'planned', NOW(), NOW()) "
                    "ON CONFLICT ON CONSTRAINT uq_scenes_project_number DO NOTHING"),
            {"id": scene_id, "pid": project_id, "sn": ref, "t": title, "loc": loc_id, "seq": order},
        )
        await session.execute(
            sa.text("INSERT INTO day_scenes (id, day_id, scene_id, order_in_day, estimated_start, "
                    "actual_status, created_at, updated_at) "
                    "VALUES (:id, :did, :sid, :o, :st, 'scheduled', NOW(), NOW())"),
            {"id": _uid(), "did": day_id, "sid": scene_id, "o": order, "st": _t(start)},
        )
        for cid in char_ids:
            await session.execute(
                sa.text("INSERT INTO scene_characters (id, scene_id, character_id, role, created_at) "
                        "VALUES (:id, :sid, :cid, 'featured', NOW())"),
                {"id": _uid(), "sid": scene_id, "cid": cid},
            )

    # Rebuild per-talent call/HMU rows for the day
    await session.execute(sa.text("DELETE FROM hmu_sessions WHERE day_id = :did"), {"did": day_id})
    for t, cid in zip([t for t in body.talent if t.name.strip()], char_ids):
        if t.effective_call or t.hmu_lead:
            await session.execute(
                sa.text("INSERT INTO hmu_sessions (id, project_id, character_id, day_id, look_id, "
                        "category, hmu_call_time, artist_lead, mold_sessions, created_at, updated_at) "
                        "VALUES (:id, :pid, :cid, :did, 'L1', 'straight', :ct, :ld, "
                        "CAST('[]' AS jsonb), NOW(), NOW())"),
                {"id": _uid(), "pid": project_id, "cid": cid, "did": day_id,
                 "ct": _t(t.effective_call), "ld": t.hmu_lead or None},
            )

    await _renumber_shoot_days(project_id, session)
    await _clear_view_cache(project_id, session)
    verb = "Edited" if was_shoot else "Added"
    who = " · ".join(first_names) or "no talent yet"
    await activity.log(session, project_id, user, "day.saved",
                       f"{verb} the {activity.fmt_day(day_date)} shoot ({who})")
    await session.commit()

    days = await build_schedule(project_id, session)
    return next(d for d in days if d["date"] == day_date.isoformat())


@router.post("/{project_id}/editorial/days/{date}/share")
async def mint_day_share_link(
    project_id: str,
    date: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    """Get-or-mint a view-only link for one day's briefing. Unlike the
    calendar link, it exposes nothing beyond this single date."""
    import secrets

    proj = await _owner_project(project_id, user, session)
    day_date = _parse_date(date)

    day = (await session.execute(
        sa.text("SELECT kind FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    if not day or day.kind != "shoot":
        raise HTTPException(status_code=404, detail="No shoot on this date")

    tokens = dict((proj.settings or {}).get("day_share_tokens", {}))
    token = tokens.get(day_date.isoformat())
    if not token:
        token = secrets.token_urlsafe(16)
        tokens[day_date.isoformat()] = token
        await session.execute(
            sa.text("UPDATE projects SET settings = settings || CAST(:p AS jsonb) WHERE id = :pid"),
            {"p": json.dumps({"day_share_tokens": tokens}), "pid": project_id},
        )
        await session.commit()
    return {"token": token, "path": f"/share/day/{token}"}


@router.post("/{project_id}/editorial/days/{date}/move")
async def move_shoot_day(
    project_id: str,
    date: str,
    body: MoveDayIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    """Move a shoot to another date. The day row keeps its id, so talent,
    segments, HMU, crew and the moodboard all travel with it; the moodboard's
    stored files and this day's todos are re-keyed to the new date."""
    proj = await _owner_project(project_id, user, session)
    src = _parse_date(date)
    dst = _parse_date(body.to)

    days = await build_schedule(project_id, session)
    if src == dst:
        return next(d for d in days if d["date"] == src.isoformat())

    src_row = (await session.execute(
        sa.text("SELECT id, kind, moodboard FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": src},
    )).first()
    if not src_row or src_row.kind != "shoot":
        raise HTTPException(status_code=404, detail="No shoot on the source date")

    dst_row = (await session.execute(
        sa.text("SELECT id, kind FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": dst},
    )).first()
    if dst_row and dst_row.kind == "shoot":
        raise HTTPException(status_code=409, detail=f"{dst.isoformat()} already has a shoot — edit or delete it first")

    # Swap dates (two-step through a sentinel date to dodge the unique constraint)
    if dst_row:
        await session.execute(
            sa.text("UPDATE days SET date = '1900-01-01' WHERE id = :id"), {"id": dst_row.id}
        )
    await session.execute(
        sa.text("UPDATE days SET date = :dt, updated_at = NOW() WHERE id = :id"),
        {"dt": dst, "id": src_row.id},
    )
    if dst_row:
        await session.execute(
            sa.text("UPDATE days SET date = :dt, updated_at = NOW() WHERE id = :id"),
            {"dt": src, "id": dst_row.id},
        )

    # Re-tag segment refs (P-MMDD → P-newMMDD); skip any that would collide
    old_tag, new_tag = src.strftime("%m%d"), dst.strftime("%m%d")
    taken = {
        r.scene_number
        for r in (await session.execute(
            sa.text("SELECT scene_number FROM scenes WHERE project_id = :pid"), {"pid": project_id}
        )).fetchall()
    }
    seg_rows = (await session.execute(
        sa.text("SELECT s.id, s.scene_number FROM scenes s "
                "JOIN day_scenes ds ON ds.scene_id = s.id WHERE ds.day_id = :did"),
        {"did": src_row.id},
    )).fetchall()
    for r in seg_rows:
        if r.scene_number.endswith(f"-{old_tag}"):
            new_ref = r.scene_number[: -len(old_tag)] + new_tag
            if new_ref not in taken:
                await session.execute(
                    sa.text("UPDATE scenes SET scene_number = :sn, updated_at = NOW() WHERE id = :id"),
                    {"sn": new_ref, "id": r.id},
                )

    # Moodboard PDFs live under date-keyed paths — copy them along
    mb = src_row.moodboard
    if mb and mb.get("kind") == "pdf":
        new_key = f"moodboards/{project_id}/{dst.isoformat()}.pdf"
        try:
            storage.put_bytes(new_key, storage.get_bytes(mb["s3_key"]), content_type="application/pdf")
            for page in range(1, mb.get("pages", 0) + 1):
                storage.put_bytes(
                    f"moodboards/{project_id}/{dst.isoformat()}/page-{page}.jpg",
                    storage.get_bytes(f"moodboards/{project_id}/{src.isoformat()}/page-{page}.jpg"),
                    content_type="image/jpeg",
                )
            await session.execute(
                sa.text("UPDATE days SET moodboard = CAST(:mb AS jsonb) WHERE id = :id"),
                {"mb": json.dumps({**mb, "s3_key": new_key}), "id": src_row.id},
            )
        except Exception:
            pass  # worst case the moodboard needs re-uploading; never block the move

    # This day's todos and its share link follow it
    settings_patch: dict = {}
    todos = (proj.settings or {}).get("todos", [])
    if any(t.get("date") == src.isoformat() for t in todos):
        settings_patch["todos"] = [
            {**t, "date": dst.isoformat()} if t.get("date") == src.isoformat() else t
            for t in todos
        ]
    day_tokens = dict((proj.settings or {}).get("day_share_tokens", {}))
    if src.isoformat() in day_tokens:
        day_tokens[dst.isoformat()] = day_tokens.pop(src.isoformat())
        settings_patch["day_share_tokens"] = day_tokens
    if settings_patch:
        await session.execute(
            sa.text("UPDATE projects SET settings = settings || CAST(:p AS jsonb) WHERE id = :pid"),
            {"p": json.dumps(settings_patch), "pid": project_id},
        )

    await _renumber_shoot_days(project_id, session)
    await _clear_view_cache(project_id, session)
    await activity.log(session, project_id, user, "day.moved",
                       f"Moved the shoot from {activity.fmt_day(src)} to {activity.fmt_day(dst)}")
    await session.commit()

    days = await build_schedule(project_id, session)
    return next(d for d in days if d["date"] == dst.isoformat())


@router.delete(
    "/{project_id}/editorial/days/{date}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_shoot_day(
    project_id: str,
    date: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    await _owner_project(project_id, user, session)
    day_date = _parse_date(date)

    day_row = (await session.execute(
        sa.text("SELECT id FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    if not day_row:
        raise HTTPException(status_code=404, detail="Day not found")

    old_scenes = (await session.execute(
        sa.text("SELECT scene_id FROM day_scenes WHERE day_id = :did"), {"did": day_row.id},
    )).fetchall()
    for r in old_scenes:
        await session.execute(sa.text("DELETE FROM scenes WHERE id = :id"), {"id": r.scene_id})
    await session.execute(sa.text("DELETE FROM hmu_sessions WHERE day_id = :did"), {"did": day_row.id})
    await session.execute(
        sa.text("UPDATE days SET kind = 'off', shoot_day_number = NULL, shift_start = NULL, "
                "shift_end = NULL, primary_location_id = NULL, banner_text = NULL, crew = NULL, "
                "moodboard = NULL, notes = NULL, updated_at = NOW() WHERE id = :id"),
        {"id": day_row.id},
    )
    await _renumber_shoot_days(project_id, session)
    await _clear_view_cache(project_id, session)
    await activity.log(session, project_id, user, "day.deleted",
                       f"Removed the {activity.fmt_day(day_date)} shoot")
    await session.commit()


# ---------------------------------------------------------------------------
# Moodboard PDF upload + view
# ---------------------------------------------------------------------------

@router.post("/{project_id}/editorial/days/{date}/moodboard")
async def upload_moodboard(
    project_id: str,
    date: str,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    day_date = _parse_date(date)

    if (file.content_type or "") != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Moodboard upload must be a PDF (or paste a link instead)")
    data = await file.read()
    if len(data) > MOODBOARD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Moodboard PDF is larger than 25 MB")

    day_row = (await session.execute(
        sa.text("SELECT id FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    if not day_row:
        raise HTTPException(status_code=404, detail="Day not found — save the shoot day first")

    key = f"moodboards/{project_id}/{day_date.isoformat()}.pdf"
    storage.put_bytes(key, data, content_type="application/pdf")
    try:
        pages = _rasterize_pdf(project_id, day_date.isoformat(), data)
    except Exception:
        pages = 0  # fall back to open-in-new-tab only
    await session.execute(
        sa.text("UPDATE days SET moodboard = CAST(:mb AS jsonb), updated_at = NOW() WHERE id = :id"),
        {"mb": json.dumps({"kind": "pdf", "s3_key": key, "filename": file.filename, "pages": pages}),
         "id": day_row.id},
    )
    await activity.log(session, project_id, user, "moodboard.uploaded",
                       f"Uploaded a moodboard for {activity.fmt_day(day_date)}"
                       + (f" ({file.filename})" if file.filename else ""))
    await session.commit()
    return {"ok": True, "kind": "pdf", "filename": file.filename, "pages": pages}


def serve_moodboard_page(project_id: str, date_iso: str, page: int, mb: dict | None):
    if not mb or mb.get("kind") != "pdf" or page < 1 or page > mb.get("pages", 0):
        raise HTTPException(status_code=404, detail="Moodboard page not found")
    img = storage.get_bytes(f"moodboards/{project_id}/{date_iso}/page-{page}.jpg")
    return Response(content=img, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{project_id}/editorial/days/{date}/moodboard/pages/{page}")
async def get_moodboard_page(
    project_id: str,
    date: str,
    page: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
):
    await _owner_project(project_id, user, session)
    day_date = _parse_date(date)
    row = (await session.execute(
        sa.text("SELECT moodboard FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    return serve_moodboard_page(project_id, day_date.isoformat(), page, row.moodboard if row else None)


def _serve_moodboard(mb: dict | None):
    """Links redirect; PDFs stream through the API so the browser never needs
    to reach the in-Docker MinIO hostname (presigned URLs sign the internal
    host, so they can't simply be rewritten)."""
    if not mb:
        raise HTTPException(status_code=404, detail="No moodboard for this day")
    if mb.get("kind") == "link":
        return RedirectResponse(url=mb["url"], status_code=302)
    pdf = storage.get_bytes(mb["s3_key"])
    filename = mb.get("filename") or "moodboard.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{project_id}/editorial/days/{date}/moodboard")
async def get_moodboard(
    project_id: str,
    date: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
):
    await _owner_project(project_id, user, session)
    day_date = _parse_date(date)
    row = (await session.execute(
        sa.text("SELECT moodboard FROM days WHERE project_id = :pid AND date = :dt"),
        {"pid": project_id, "dt": day_date},
    )).first()
    return _serve_moodboard(row.moodboard if row else None)


# ---------------------------------------------------------------------------
# Producer to-do list (never exposed through /share)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/todos")
async def get_todos(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    row = await _owner_project(project_id, user, session)
    return {"todos": (row.settings or {}).get("todos", [])}


@router.put("/{project_id}/markers")
async def save_markers(
    project_id: str,
    body: MarkersIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    proj = await _owner_project(project_id, user, session)
    markers = [m.model_dump() for m in body.markers]
    await session.execute(
        sa.text("UPDATE projects SET settings = settings || CAST(:patch AS jsonb) WHERE id = :pid"),
        {"patch": json.dumps({"markers": markers}), "pid": project_id},
    )
    old = {m.get("id"): m for m in (proj.settings or {}).get("markers", [])}
    new = {m["id"]: m for m in markers}
    lines = [
        f"Added special day “{m['label']}” on {activity.fmt_day(m['date'])}"
        for i, m in new.items() if i not in old
    ] + [
        f"Removed special day “{m['label']}” ({activity.fmt_day(m['date'])})"
        for i, m in old.items() if i not in new
    ]
    await activity.log(session, project_id, user, "markers.updated",
                       "; ".join(lines) or "Updated special days")
    await session.commit()
    return {"markers": markers}


@router.put("/{project_id}/todos")
async def save_todos(
    project_id: str,
    body: TodosIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    proj = await _owner_project(project_id, user, session)
    todos = [t.model_dump() for t in body.todos]
    await session.execute(
        sa.text("UPDATE projects SET settings = settings || CAST(:patch AS jsonb) WHERE id = :pid"),
        {"patch": json.dumps({"todos": todos}), "pid": project_id},
    )
    await activity.log(session, project_id, user, "todos.updated",
                       _todo_change_summary((proj.settings or {}).get("todos", []), todos))
    await session.commit()
    return {"todos": todos}


def _todo_change_summary(old_list: list[dict], new_list: list[dict]) -> str:
    def clip(text: str) -> str:
        return text if len(text) <= 48 else text[:45] + "…"

    def day(t: dict) -> str:
        return f" ({activity.fmt_day(t['date'])})" if t.get("date") else ""

    old = {t.get("id"): t for t in old_list}
    new = {t["id"]: t for t in new_list}
    lines = [f"Added to-do “{clip(t['text'])}”{day(t)}" for i, t in new.items() if i not in old]
    lines += [f"Deleted to-do “{clip(t['text'])}”{day(t)}" for i, t in old.items() if i not in new]
    for i, t in new.items():
        if i in old and bool(old[i].get("done")) != bool(t.get("done")):
            verb = "Ticked off" if t.get("done") else "Reopened"
            lines.append(f"{verb} “{clip(t['text'])}”{day(t)}")
    return "; ".join(lines) or "Updated to-dos"


# ---------------------------------------------------------------------------
# Activity log — who changed what (producers only)
# ---------------------------------------------------------------------------

@router.get("/{project_id}/activity")
async def get_activity(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    rows = (await session.execute(
        sa.text("SELECT id, user_email, action, summary, created_at FROM activity_log "
                "WHERE project_id = :pid ORDER BY created_at DESC LIMIT 150"),
        {"pid": project_id},
    )).fetchall()
    return {
        "items": [
            {
                "id": r.id,
                "user_email": r.user_email,
                "action": r.action,
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
