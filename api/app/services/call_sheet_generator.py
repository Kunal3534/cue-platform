"""CallSheetGenerator — render a day's call sheet as PDF, upload to S3, and
create/version a call_sheets row.

Usage:
    sheet = await CallSheetGenerator.generate(project_id, day_id, user_id, session)
    # sheet.pdf_s3_key  → S3 key for the PDF
    # sheet.version     → monotonic version number for this day
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from .project_graph import ProjectGraph, fmt_pages, fmt_shift
from . import storage
from ..models import CallSheet

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["fmt_pages"] = fmt_pages
    return env


def _dn_label(dn: str | None) -> str:
    mapping = {
        "day": "DAY EXT",
        "night": "NIGHT EXT",
        "day_int": "DAY INT",
        "night_int": "NIGHT INT",
        "dusk": "DUSK/GOLDEN HR",
    }
    return mapping.get(dn or "day", (dn or "DAY").upper())


def _render_html(pg: ProjectGraph, day_id: str, version: int, prev_version: int | None) -> str:
    day = next((d for d in pg.days if d.id == day_id), None)
    if day is None:
        raise ValueError(f"Day {day_id} not found in project graph")

    char_by_name = {c.canonical_name: c for c in pg.characters}
    cast = [char_by_name[cn] for cn in day.cast if cn in char_by_name]

    day_jr_calls = [j for j in pg.jr_calls if j.day_id == day_id]

    # Page totals
    total_pages_eighths = sum(sc.page_eighths or 0 for sc in day.scenes)
    total_setups = sum(sc.setups_est for sc in day.scenes)

    # Weather summary from day.notes or weather JSONB (bare-bones)
    weather_summary = None

    # Date formatting
    date_obj = day.date
    day_of_week = date_obj.strftime("%A")
    date_formatted = date_obj.strftime("%-d %B %Y")

    # Shift
    shift = fmt_shift(day.shift_start, day.shift_end) or None

    context = {
        "project_title": pg.project.title,
        "shoot_day_number": day.shoot_day_number or 0,
        "dn_label": _dn_label(day.scenes[0].dn if day.scenes else None),
        "location_name": day.location_name,
        "location_area": day.location_area,
        "day_of_week": day_of_week,
        "date_formatted": date_formatted,
        "shift": shift,
        # timing grid stubs — can be populated from day.shift_start/end
        "crew_call": day.shift_start.strftime("%H:%M") if day.shift_start else None,
        "cast_call": None,
        "first_shot": None,
        "wrap_target": day.shift_end.strftime("%H:%M") if day.shift_end else None,
        "sunrise": None,
        "golden_hour": None,
        "sunset": None,
        "weather_summary": weather_summary,
        # location extras (not in DB yet — placeholder)
        "unit_base": None,
        "hospital": None,
        "banner_text": day.banner_text,
        "scenes": day.scenes,
        "total_pages": fmt_pages(total_pages_eighths),
        "total_setups": total_setups,
        "cast": cast,
        "jr_calls": day_jr_calls,
        "vehicle_names": day.vehicle_names,
        "camera_uses": day.camera_uses,
        "day_notes": day.notes,
        "version": version,
        "prev_version": prev_version,
        "generated_at": datetime.now(timezone.utc).strftime("%I:%M %p · %d %b %Y"),
    }
    env = _jinja_env()
    template = env.get_template("callsheet.html")
    return template.render(**context)


async def _editorial_data(project_id: str, day_id: str, session: AsyncSession) -> dict | None:
    """Return editorial call-sheet data, or None when the project is not in
    editorial mode (film projects keep the classic template)."""
    proj = (await session.execute(
        sa.text("SELECT settings FROM projects WHERE id = :pid"),
        {"pid": project_id},
    )).first()
    if not proj or (proj.settings or {}).get("mode") != "editorial":
        return None

    day = (await session.execute(
        sa.text("SELECT kind FROM days WHERE id = :did"),
        {"did": day_id},
    )).first()

    seg_rows = (await session.execute(
        sa.text("""
            SELECT s.id, s.scene_number, s.title, s.description,
                   ds.estimated_start, ds.estimated_duration_minutes
            FROM day_scenes ds
            JOIN scenes s ON s.id = ds.scene_id
            WHERE ds.day_id = :did
            ORDER BY ds.order_in_day
        """),
        {"did": day_id},
    )).fetchall()

    talent_rows = (await session.execute(
        sa.text("""
            SELECT DISTINCT c.id, c.display_name, c.actor_contact, c.is_principal, c.notes
            FROM scene_characters sc
            JOIN characters c ON c.id = sc.character_id
            JOIN day_scenes ds ON ds.scene_id = sc.scene_id
            WHERE ds.day_id = :did
            ORDER BY c.is_principal DESC, c.display_name
        """),
        {"did": day_id},
    )).fetchall()

    seg_talent_rows = (await session.execute(
        sa.text("""
            SELECT sc.scene_id, c.display_name
            FROM scene_characters sc
            JOIN characters c ON c.id = sc.character_id
            JOIN day_scenes ds ON ds.scene_id = sc.scene_id
            WHERE ds.day_id = :did
        """),
        {"did": day_id},
    )).fetchall()

    hmu_rows = (await session.execute(
        sa.text("""
            SELECT character_id, hmu_call_time, artist_lead
            FROM hmu_sessions WHERE day_id = :did
        """),
        {"did": day_id},
    )).fetchall()

    look_rows = (await session.execute(
        sa.text("""
            SELECT character_id, look_id, description
            FROM wardrobe_looks WHERE project_id = :pid
        """),
        {"pid": project_id},
    )).fetchall()

    talent_by_seg: dict[str, list[str]] = {}
    for r in seg_talent_rows:
        talent_by_seg.setdefault(r.scene_id, []).append(r.display_name)

    segments = [
        {
            "scene_number": r.scene_number,
            "title": r.title,
            "description": r.description,
            "start": r.estimated_start.strftime("%H:%M") if r.estimated_start else None,
            "duration_minutes": r.estimated_duration_minutes,
            "talent": sorted(talent_by_seg.get(r.id, [])),
        }
        for r in seg_rows
    ]

    hmu_by_char = {r.character_id: r for r in hmu_rows}
    looks_by_char: dict[str, list[str]] = {}
    for r in look_rows:
        label = f"{r.look_id}" + (f" — {r.description}" if r.description else "")
        looks_by_char.setdefault(r.character_id, []).append(label)

    def _contact(raw: dict | None) -> str | None:
        if not raw:
            return None
        parts = [raw.get("manager"), raw.get("phone"), raw.get("email")]
        return " · ".join(p for p in parts if p) or None

    talent = [
        {
            "display_name": r.display_name,
            "is_principal": r.is_principal,
            "role_label": r.notes,
            "hmu_call": (
                hmu_by_char[r.id].hmu_call_time.strftime("%H:%M")
                if r.id in hmu_by_char and hmu_by_char[r.id].hmu_call_time else None
            ),
            "hmu_lead": hmu_by_char[r.id].artist_lead if r.id in hmu_by_char else None,
            "looks": looks_by_char.get(r.id, []),
            "contact": _contact(r.actor_contact),
        }
        for r in talent_rows
    ]

    hmu_calls = [t["hmu_call"] for t in talent if t["hmu_call"]]
    seg_starts = [s["start"] for s in segments if s["start"]]

    return {
        "day_kind": day.kind if day else "shoot",
        "segments": segments,
        "talent": talent,
        "first_hmu_call": min(hmu_calls) if hmu_calls else None,
        "first_on_set": min(seg_starts) if seg_starts else None,
    }


def _render_html_editorial(
    pg: ProjectGraph, day_id: str, version: int, prev_version: int | None, ed: dict
) -> str:
    day = next((d for d in pg.days if d.id == day_id), None)
    if day is None:
        raise ValueError(f"Day {day_id} not found in project graph")

    date_obj = day.date
    context = {
        "project_title": pg.project.title,
        "shoot_day_number": day.shoot_day_number,
        "day_kind": ed["day_kind"],
        "day_headline": day.banner_text,
        "location_name": day.location_name,
        "location_area": day.location_area,
        "day_of_week": date_obj.strftime("%A"),
        "date_formatted": date_obj.strftime("%-d %B %Y"),
        "shift": fmt_shift(day.shift_start, day.shift_end) or None,
        "crew_call": day.shift_start.strftime("%H:%M") if day.shift_start else None,
        "wrap_target": day.shift_end.strftime("%H:%M") if day.shift_end else None,
        "first_hmu_call": ed["first_hmu_call"],
        "first_on_set": ed["first_on_set"],
        "banner_text": None,  # shown as the headline instead
        "segments": ed["segments"],
        "talent": ed["talent"],
        "day_notes": day.notes,
        "version": version,
        "prev_version": prev_version,
        "generated_at": datetime.now(timezone.utc).strftime("%I:%M %p · %d %b %Y"),
    }
    env = _jinja_env()
    template = env.get_template("callsheet_editorial.html")
    return template.render(**context)


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


class CallSheetGenerator:

    @staticmethod
    async def generate(
        project_id: str,
        day_id: str,
        user_id: str,
        session: AsyncSession,
        scenario_id: str | None = None,
    ) -> CallSheet:
        # Determine next version number
        last = (await session.execute(
            sa.select(sa.func.max(CallSheet.version))
            .where(CallSheet.day_id == day_id)
        )).scalar()
        prev_version = last
        version = (last or 0) + 1

        # Load project data
        pg = await ProjectGraph.load(project_id, scenario_id, session)

        # Render HTML → PDF (editorial projects get the editorial template)
        editorial = await _editorial_data(project_id, day_id, session)
        if editorial is not None:
            html = _render_html_editorial(pg, day_id, version, prev_version, editorial)
        else:
            html = _render_html(pg, day_id, version, prev_version)
        pdf_bytes = _html_to_pdf(html)

        # Upload to S3
        key = storage.key_callsheet(project_id, day_id, version)
        storage.put_bytes(key, pdf_bytes, content_type="application/pdf")

        # Persist call_sheets row
        sheet = CallSheet(
            id=str(uuid.uuid4()),
            project_id=project_id,
            day_id=day_id,
            version=version,
            status="ready",
            pdf_s3_key=key,
            generated_at=datetime.now(timezone.utc),
            generated_by=user_id,
        )
        session.add(sheet)
        await session.commit()
        await session.refresh(sheet)
        return sheet

    @staticmethod
    async def get_latest(day_id: str, session: AsyncSession) -> CallSheet | None:
        result = await session.execute(
            sa.select(CallSheet)
            .where(CallSheet.day_id == day_id)
            .order_by(CallSheet.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
