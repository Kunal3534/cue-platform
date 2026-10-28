"""Producer-only shoot expenses.

Receipts/bills upload as images or PDFs; a background job reads each one and
fills in vendor, amount, category and line items. Producers can also enter
expenses by hand, correct anything the reader got wrong, and export the whole
thing as a slide deck (.pptx — opens directly in Google Slides) for the
Condé Nast accounts team.

Every route requires an authenticated team member. Nothing here is ever
reachable through /share links.
"""
from __future__ import annotations

import json
import uuid
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_async_db
from ..models import User
from ..services import activity, storage
from .editorial import _owner_project

router = APIRouter(prefix="/projects", tags=["expenses"])

RECEIPT_MAX_BYTES = 15 * 1024 * 1024
RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}

CATEGORIES = [
    "travel", "food", "location", "equipment", "styling", "hmu",
    "production", "misc",
]


class ExpenseIn(BaseModel):
    date: str | None = None  # shoot day this belongs to (ISO), null = general
    vendor: str | None = None
    description: str | None = None
    category: str | None = None
    amount: float | None = None
    currency: str = "INR"
    notes: str | None = None


class ExpensePatch(BaseModel):
    date: str | None = None
    clear_date: bool = False  # explicit — None above means "leave as is"
    vendor: str | None = None
    description: str | None = None
    category: str | None = None
    amount: float | None = None
    currency: str | None = None
    notes: str | None = None
    approve: bool = False  # sign off a "Check details" row as-is


def _amount(v: float | None) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise HTTPException(status_code=422, detail=f"Bad amount: {v!r}")


def _date_or_none(raw: str | None) -> date_cls | None:
    if not raw:
        return None
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Bad date: {raw!r}")


def _row_out(r) -> dict:
    return {
        "id": r.id,
        "date": r.date.isoformat() if r.date else None,
        "vendor": r.vendor,
        "description": r.description,
        "category": r.category,
        "amount": float(r.amount) if r.amount is not None else None,
        "currency": r.currency,
        "source": r.source,
        "has_receipt": bool(r.s3_key),
        "filename": r.filename,
        "content_type": r.content_type,
        "status": r.status,
        "extracted": r.extracted,
        "notes": r.notes,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat(),
    }


_SELECT = ("SELECT id, date, vendor, description, category, amount, currency, source, "
           "s3_key, filename, content_type, status, extracted, notes, created_by, created_at "
           "FROM expenses")


async def _expense(session: AsyncSession, project_id: str, expense_id: str):
    row = (await session.execute(
        sa.text(f"{_SELECT} WHERE project_id = :pid AND id = :eid"),
        {"pid": project_id, "eid": expense_id},
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Expense not found")
    return row


def _label(row) -> str:
    bits = [b for b in (row.vendor, row.description) if b]
    label = bits[0] if bits else (row.filename or "expense")
    return label if len(label) <= 40 else label[:37] + "…"


# ---------------------------------------------------------------------------
# List / create / edit / delete
# ---------------------------------------------------------------------------

@router.get("/{project_id}/expenses")
async def list_expenses(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    rows = (await session.execute(
        sa.text(f"{_SELECT} WHERE project_id = :pid ORDER BY date NULLS LAST, created_at DESC"),
        {"pid": project_id},
    )).fetchall()
    items = [_row_out(r) for r in rows]
    by_date: dict[str, float] = {}
    grand = 0.0
    for it in items:
        if it["amount"] is not None:
            key = it["date"] or "general"
            by_date[key] = round(by_date.get(key, 0.0) + it["amount"], 2)
            grand = round(grand + it["amount"], 2)
    return {"items": items, "totals": {"by_date": by_date, "grand": grand},
            "categories": CATEGORIES}


@router.post("/{project_id}/expenses")
async def create_expense(
    project_id: str,
    body: ExpenseIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    eid = str(uuid.uuid4())
    await session.execute(
        sa.text("INSERT INTO expenses (id, project_id, date, vendor, description, category, "
                "amount, currency, source, status, notes, created_by, created_at, updated_at) "
                "VALUES (:id, :pid, :dt, :vn, :ds, :cat, :am, :cur, 'manual', 'ready', :nt, "
                ":by, NOW(), NOW())"),
        {"id": eid, "pid": project_id, "dt": _date_or_none(body.date),
         "vn": body.vendor or None, "ds": body.description or None,
         "cat": body.category or None, "am": _amount(body.amount),
         "cur": (body.currency or "INR").upper()[:8], "nt": body.notes or None,
         "by": user.email},
    )
    row = await _expense(session, project_id, eid)
    when = f" ({activity.fmt_day(row.date)})" if row.date else ""
    await activity.log(session, project_id, user, "expense.added",
                       f"Added expense “{_label(row)}”{when}")
    await session.commit()
    return _row_out(row)


@router.post("/{project_id}/expenses/upload")
async def upload_receipt(
    project_id: str,
    file: UploadFile = File(...),
    date: str | None = Form(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    shoot_date = _date_or_none(date)

    ctype = (file.content_type or "").lower()
    name = (file.filename or "").lower()
    if ctype not in RECEIPT_TYPES and not name.endswith((".jpg", ".jpeg", ".png", ".webp", ".pdf")):
        raise HTTPException(status_code=422,
                            detail="Upload a photo (JPEG/PNG/WebP) or PDF of the receipt")
    data = await file.read()
    if len(data) > RECEIPT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Receipt file is larger than 15 MB")
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")

    eid = str(uuid.uuid4())
    ext = ".pdf" if (ctype == "application/pdf" or name.endswith(".pdf")) else ".jpg" \
        if not name.endswith((".png", ".webp")) else name[name.rfind("."):]
    key = f"expenses/{project_id}/{eid}{ext}"
    storage.put_bytes(key, data, content_type=ctype or "application/octet-stream")

    await session.execute(
        sa.text("INSERT INTO expenses (id, project_id, date, currency, source, s3_key, filename, "
                "content_type, status, created_by, created_at, updated_at) "
                "VALUES (:id, :pid, :dt, 'INR', 'receipt', :k, :fn, :ct, 'processing', :by, "
                "NOW(), NOW())"),
        {"id": eid, "pid": project_id, "dt": shoot_date, "k": key,
         "fn": file.filename or None, "ct": ctype or None, "by": user.email},
    )
    when = f" for {activity.fmt_day(shoot_date)}" if shoot_date else ""
    await activity.log(session, project_id, user, "expense.uploaded",
                       f"Uploaded a receipt{when}"
                       + (f" ({file.filename})" if file.filename else ""))
    await session.commit()

    # Hand the receipt to the worker to read; if the queue is unreachable the
    # row simply stays editable by hand.
    try:
        from arq import create_pool

        from ..worker import get_redis_settings
        pool = await create_pool(get_redis_settings())
        await pool.enqueue_job("extract_expense", eid)
    except Exception:
        await session.execute(
            sa.text("UPDATE expenses SET status = 'needs_review', updated_at = NOW() WHERE id = :id"),
            {"id": eid},
        )
        await session.commit()

    row = await _expense(session, project_id, eid)
    return _row_out(row)


@router.post("/{project_id}/expenses/{expense_id}/reread")
async def reread_receipt(
    project_id: str,
    expense_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    """Queue a receipt for another reading pass — e.g. after the first one
    failed, or after the AI key was fixed. No re-upload needed."""
    await _owner_project(project_id, user, session)
    row = await _expense(session, project_id, expense_id)
    if not row.s3_key:
        raise HTTPException(status_code=422, detail="This expense has no receipt file to read")

    await session.execute(
        sa.text("UPDATE expenses SET status = 'processing', updated_at = NOW() "
                "WHERE id = :eid AND project_id = :pid"),
        {"eid": expense_id, "pid": project_id},
    )
    await session.commit()
    try:
        from arq import create_pool

        from ..worker import get_redis_settings
        pool = await create_pool(get_redis_settings())
        await pool.enqueue_job("extract_expense", expense_id)
    except Exception:
        await session.execute(
            sa.text("UPDATE expenses SET status = 'needs_review', updated_at = NOW() WHERE id = :eid"),
            {"eid": expense_id},
        )
        await session.commit()
        raise HTTPException(status_code=503, detail="Could not reach the reader — try again in a minute")
    return {"ok": True}


@router.patch("/{project_id}/expenses/{expense_id}")
async def update_expense(
    project_id: str,
    expense_id: str,
    body: ExpensePatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> dict:
    await _owner_project(project_id, user, session)
    await _expense(session, project_id, expense_id)

    sets, params = ["updated_at = NOW()", "status = 'ready'"], {}
    if body.clear_date:
        sets.append("date = NULL")
    elif body.date is not None:
        sets.append("date = :dt")
        params["dt"] = _date_or_none(body.date)
    for field, value in (("vendor", body.vendor), ("description", body.description),
                         ("category", body.category), ("notes", body.notes)):
        if value is not None:
            sets.append(f"{field} = :{field}")
            params[field] = value.strip() or None
    if body.amount is not None:
        sets.append("amount = :am")
        params["am"] = _amount(body.amount)
    if body.currency is not None:
        sets.append("currency = :cur")
        params["cur"] = body.currency.upper()[:8]

    changed_fields = bool(params) or body.clear_date
    await session.execute(
        sa.text(f"UPDATE expenses SET {', '.join(sets)} WHERE id = :eid AND project_id = :pid"),
        {**params, "eid": expense_id, "pid": project_id},
    )
    row = await _expense(session, project_id, expense_id)
    if body.approve and not changed_fields:
        verb, action = "Approved", "expense.approved"
    else:
        verb, action = "Updated", "expense.updated"
    amt = f" — ₹{float(row.amount):,.2f}" if body.approve and row.amount is not None else ""
    await activity.log(session, project_id, user, action,
                       f"{verb} expense “{_label(row)}”{amt}")
    await session.commit()
    return _row_out(row)


@router.delete(
    "/{project_id}/expenses/{expense_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_expense(
    project_id: str,
    expense_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
) -> None:
    await _owner_project(project_id, user, session)
    row = await _expense(session, project_id, expense_id)
    if row.s3_key:
        try:
            storage.delete(row.s3_key)
        except Exception:
            pass  # orphaned object is harmless; never block the delete
    await session.execute(
        sa.text("DELETE FROM expenses WHERE id = :eid AND project_id = :pid"),
        {"eid": expense_id, "pid": project_id},
    )
    await activity.log(session, project_id, user, "expense.deleted",
                       f"Deleted expense “{_label(row)}”")
    await session.commit()


@router.get("/{project_id}/expenses/{expense_id}/receipt")
async def get_receipt(
    project_id: str,
    expense_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
):
    await _owner_project(project_id, user, session)
    row = await _expense(session, project_id, expense_id)
    if not row.s3_key:
        raise HTTPException(status_code=404, detail="No receipt file on this expense")
    data = storage.get_bytes(row.s3_key)
    filename = row.filename or "receipt"
    return Response(
        content=data,
        media_type=row.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{filename}"',
                 "Cache-Control": "private, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Report — a slide deck for the accounts team
# ---------------------------------------------------------------------------

@router.get("/{project_id}/expenses/report.pptx")
async def expense_report(
    project_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_db),
):
    await _owner_project(project_id, user, session)
    proj = (await session.execute(
        sa.text('SELECT title FROM projects WHERE id = :pid'), {"pid": project_id},
    )).first()
    rows = (await session.execute(
        sa.text(f"{_SELECT} WHERE project_id = :pid ORDER BY date NULLS LAST, created_at"),
        {"pid": project_id},
    )).fetchall()
    day_rows = (await session.execute(
        sa.text("SELECT date, banner_text FROM days "
                "WHERE project_id = :pid AND kind = 'shoot' ORDER BY date"),
        {"pid": project_id},
    )).fetchall()

    from ..services.reports.expense_deck import build_deck
    items = []
    for r in rows:
        d = _row_out(r)
        d["s3_key"] = r.s3_key  # deck embeds receipt images; key never leaves the API
        items.append(d)
    deck = build_deck(
        project_title=proj.title if proj else "GQ Men of the Year",
        expenses=items,
        shoot_headlines={d.date.isoformat(): d.banner_text for d in day_rows},
    )
    await activity.log(session, project_id, user, "expenses.exported",
                       "Exported the expense report deck")
    await session.commit()
    return Response(
        content=deck,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="GQ-MOTY-expense-report.pptx"'},
    )
