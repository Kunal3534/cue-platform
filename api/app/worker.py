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
    """Parse ``redis_url`` into RedisSettings.

    Handles all common shapes:
        redis://host:6379
        redis://host:6379/0
        redis://:PASSWORD@host:6379
        redis://USERNAME:PASSWORD@host:6379/0   (Railway / Upstash style)
        rediss://...                             (TLS)
    """
    url = settings.redis_url
    if not url:
        return RedisSettings()
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        username=parsed.username,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


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
# Task: extract_expense — read a receipt image/PDF into structured fields
# ---------------------------------------------------------------------------

EXPENSE_CATEGORIES = {"travel", "food", "location", "equipment", "styling",
                      "hmu", "production", "misc"}

_EXPENSE_PROMPT = """You are reading a receipt, bill, invoice or payment screenshot
from a magazine photo-shoot production in India. Extract what was spent.

Reply with ONLY a JSON object, no prose and no code fences:
{
  "vendor": "who was paid (store/service name), or null",
  "receipt_date": "YYYY-MM-DD or null",
  "currency": "ISO code, e.g. INR",
  "total_amount": 1234.50,
  "category": "one of: travel, food, location, equipment, styling, hmu, production, misc",
  "description": "one short line saying what this was for",
  "line_items": [{"description": "...", "amount": 123.0}]
}
Use null for anything you cannot read. total_amount is the final amount paid
(after taxes/tips). If several payments appear, total_amount is their sum."""


def _receipt_images(data: bytes, content_type: str | None) -> list[bytes]:
    """Receipt file → one or more JPEGs sized for the model."""
    from PIL import Image

    def shrink(img) -> bytes:
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    if (content_type or "").endswith("pdf") or data[:5] == b"%PDF-":
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(data)
        pages = [shrink(doc[i].render(scale=2.0).to_pil()) for i in range(min(len(doc), 3))]
        doc.close()
        return pages
    return [shrink(Image.open(io.BytesIO(data)))]


async def extract_expense(ctx: dict, expense_id: str) -> dict:
    """Fill in an uploaded expense's fields by reading its receipt."""
    import base64
    import json as _json

    import sqlalchemy as sa

    async with async_session_factory() as session:
        row = (await session.execute(
            sa.text("SELECT id, s3_key, content_type, status FROM expenses WHERE id = :id"),
            {"id": expense_id},
        )).first()
        if not row or row.status != "processing" or not row.s3_key:
            return {"skipped": True}

        async def finish(status: str, extracted: dict, fields: dict | None = None) -> None:
            sets = ["status = :st", "extracted = CAST(:ex AS jsonb)", "updated_at = NOW()"]
            params: dict = {"st": status, "ex": _json.dumps(extracted), "id": expense_id}
            for col, val in (fields or {}).items():
                sets.append(f"{col} = :{col}")
                params[col] = val
            # Only land results if nobody edited the row while we were reading
            await session.execute(
                sa.text(f"UPDATE expenses SET {', '.join(sets)} "
                        "WHERE id = :id AND status = 'processing'"),
                params,
            )
            await session.commit()

        if not settings.anthropic_api_key:
            await finish("needs_review", {"error": "no_api_key"})
            return {"status": "needs_review", "reason": "no_api_key"}

        try:
            images = _receipt_images(storage.get_bytes(row.s3_key), row.content_type)
        except Exception as exc:
            await finish("needs_review", {"error": f"unreadable file: {exc}"})
            return {"status": "needs_review"}

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            content: list[dict] = [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg",
                            "data": base64.b64encode(img).decode()}}
                for img in images
            ]
            content.append({"type": "text", "text": _EXPENSE_PROMPT})
            msg = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1500,
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text").strip()
            if text.startswith("```"):
                text = text.strip("`").removeprefix("json").strip()
            parsed = _json.loads(text[text.index("{"): text.rindex("}") + 1])
        except Exception as exc:
            await finish("needs_review", {"error": f"extraction failed: {exc}"})
            return {"status": "needs_review"}

        from decimal import Decimal, InvalidOperation
        amount = None
        try:
            if parsed.get("total_amount") is not None:
                amount = Decimal(str(parsed["total_amount"])).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            amount = None
        category = parsed.get("category")
        fields = {
            "vendor": (parsed.get("vendor") or None),
            "description": (parsed.get("description") or None),
            "category": category if category in EXPENSE_CATEGORIES else "misc",
            "amount": amount,
            "currency": (parsed.get("currency") or "INR").upper()[:8],
        }
        # Always land on needs_review: a producer approves every auto-read
        # amount before it counts as checked (Approve button in the UI).
        await finish("needs_review", parsed, fields)
        return {"status": "needs_review", "amount": str(amount) if amount is not None else None}


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
    functions = [regenerate_views, regenerate_call_sheet, send_call_sheet, export_bundle,
                 run_flag_detector, extract_expense]
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
