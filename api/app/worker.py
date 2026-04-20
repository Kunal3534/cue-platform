"""Arq async worker — heavy background tasks.

Tasks:
  regenerate_views      — rebuild one or more view_cache entries
  regenerate_call_sheet — render PDF + upload to S3 + version call_sheets row
  send_call_sheet       — email the PDF (stub; Week 6 Resend wiring)
  export_bundle         — generate all 14 xlsx + zip → S3
  run_flag_detector     — run all flag rules; upsert flags; publish SSE events
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from .config import settings
from .db import async_session_factory
from .services import storage
from .services.project_graph import ProjectGraph
from .services.call_sheet_generator import CallSheetGenerator


# ---------------------------------------------------------------------------
# arq Redis settings helper
# ---------------------------------------------------------------------------

def get_redis_settings() -> RedisSettings:
    url = settings.redis_url  # e.g. "redis://redis:6379/0"
    # arq RedisSettings accepts host/port/db separately
    import re
    m = re.match(r"redis://([^:/]+)(?::(\d+))?(?:/(\d+))?", url)
    if m:
        host = m.group(1)
        port = int(m.group(2) or 6379)
        db = int(m.group(3) or 0)
        return RedisSettings(host=host, port=port, database=db)
    return RedisSettings()


# ---------------------------------------------------------------------------
# Task: regenerate_views
# ---------------------------------------------------------------------------

async def regenerate_views(ctx: dict, project_id: str, view_names: list[str], scenario_id: str | None = None) -> dict:
    """Regenerate and cache the specified views for a project."""
    from .services.views import main_schedule as _ms
    from .services.views import calendar as _cal
    from .services.views import scenes_matrix as _sm
    from .services.views import cast_dood as _dood

    renderers = {
        "main_schedule": _ms.render,
        "calendar": _cal.render,
        "scenes_matrix": _sm.render,
        "cast_dood": _dood.render,
    }

    async with async_session_factory() as session:
        results = {}
        for name in view_names:
            renderer = renderers.get(name)
            if renderer is None:
                results[name] = "unknown_view"
                continue
            try:
                await renderer(project_id, scenario_id, session, use_cache=False)
                results[name] = "ok"
            except Exception as exc:
                results[name] = f"error: {exc}"
        return results


# ---------------------------------------------------------------------------
# Task: regenerate_call_sheet
# ---------------------------------------------------------------------------

async def regenerate_call_sheet(ctx: dict, project_id: str, day_id: str, user_id: str, scenario_id: str | None = None) -> dict:
    """Render PDF for a shoot day, upload to S3, record in call_sheets."""
    from .services import sse as _sse
    async with async_session_factory() as session:
        sheet = await CallSheetGenerator.generate(project_id, day_id, user_id, session, scenario_id)
    await _sse.publish(project_id, {
        "kind": "call_sheet_regenerated",
        "day_id": day_id,
        "call_sheet_id": sheet.id,
        "version": sheet.version,
    })
    return {
        "call_sheet_id": sheet.id,
        "version": sheet.version,
        "pdf_s3_key": sheet.pdf_s3_key,
    }


# ---------------------------------------------------------------------------
# Task: send_call_sheet
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Task: run_flag_detector
# ---------------------------------------------------------------------------

async def run_flag_detector(ctx: dict, project_id: str, scenario_id: str | None = None) -> dict:
    """Run all flag rules for a project; write results to flags table."""
    from .services.flag_detector import FlagDetector
    async with async_session_factory() as session:
        return await FlagDetector.run(project_id, scenario_id, session)


# ---------------------------------------------------------------------------
# Task: send_call_sheet
# ---------------------------------------------------------------------------

async def send_call_sheet(ctx: dict, call_sheet_id: str, recipients: list[dict]) -> dict:
    """Email call sheet PDF via Resend (stub — Week 6)."""
    # TODO Week 6 — call Resend API, update sent_at / sent_to on call_sheets row
    return {"status": "stub", "call_sheet_id": call_sheet_id, "recipients": len(recipients)}


# ---------------------------------------------------------------------------
# Task: export_bundle
# ---------------------------------------------------------------------------

_REPORT_MODULES = [
    ("main_schedule",  "main_schedule"),
    ("cast_dood",      "cast_dood"),
    ("scenes_matrix",  "scenes_matrix"),
    ("calendar",       "calendar"),
    ("vehicles",       "vehicles"),
    ("cameras",        "cameras"),
    ("juniors",        "juniors"),
    ("props",          "props"),
    ("animals",        "animals"),
    ("vfx",            "vfx"),
    ("sfx_stunts",     "sfx_stunts"),
    ("hmu",            "hmu"),
    ("wardrobe",       "wardrobe"),
    ("requirements",   "requirements"),
]


async def export_bundle(ctx: dict, project_id: str, job_id: str, scenario_id: str | None = None) -> dict:
    """Generate all 14 xlsx reports, zip them, upload to S3."""
    import importlib

    async with async_session_factory() as session:
        pg = await ProjectGraph.load(project_id, scenario_id, session)

    storage.ensure_bucket()

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for view_name, module_name in _REPORT_MODULES:
                mod = importlib.import_module(f".services.reports.{module_name}", package="app")
                out_path = os.path.join(tmpdir, f"{view_name}.xlsx")
                try:
                    mod.generate(pg, out_path)
                    zf.write(out_path, f"{view_name}.xlsx")
                    # Also upload individual xlsx
                    xlsx_key = storage.key_export_xlsx(project_id, view_name)
                    storage.put_file(xlsx_key, out_path, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as exc:
                    # Log and continue; don't abort the whole bundle
                    print(f"[worker] export_bundle: {view_name} failed: {exc}")

        zip_bytes = zip_buf.getvalue()
        zip_key = storage.key_export_zip(project_id, job_id)
        storage.put_bytes(zip_key, zip_bytes, content_type="application/zip")

    return {"job_id": job_id, "zip_key": zip_key}


# ---------------------------------------------------------------------------
# arq WorkerSettings
# ---------------------------------------------------------------------------

class WorkerSettings:
    functions = [regenerate_views, regenerate_call_sheet, send_call_sheet, export_bundle, run_flag_detector]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 300  # 5 min


# ---------------------------------------------------------------------------
# Entrypoint: python -m app.worker
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    from arq import run_worker
    run_worker(WorkerSettings)
