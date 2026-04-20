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

        # Render HTML → PDF
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
