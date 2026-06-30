import json
import os
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, UploadFile

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api/expenses", dependencies=[Depends(verify_auth)])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")


def _parse_attachments(raw):
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except Exception:
        return []


async def _store_uploads(files):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored = []
    if not files:
        return stored
    for f in files:
        if f.filename:
            ext = os.path.splitext(f.filename)[1]
            filename = f"{uuid.uuid4().hex}{ext}"
            path = os.path.join(UPLOAD_DIR, filename)
            with open(path, "wb") as out:
                out.write(await f.read())
            stored.append(filename)
    return stored


@router.post("", status_code=201)
async def create_expense(
    date: str = Form(...),
    title: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("PLN"),
    vendor: str = Form(None),
    category: str = Form(None),
    kind: str = Form("reimbursable"),
    reimbursement_status: str = Form("pending"),
    request_id: int = Form(None),
    notes: str = Form(None),
    attachments: list[UploadFile] = File(None),
):
    attachment_paths = await _store_uploads(attachments)
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO expenses
               (date, title, vendor, amount, currency, category, kind, reimbursement_status, request_id, notes, attachments)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date,
                title,
                vendor,
                amount,
                currency or "PLN",
                category,
                kind or "reimbursable",
                reimbursement_status or "pending",
                request_id,
                notes,
                json.dumps(attachment_paths) if attachment_paths else None,
            ),
        )
        db.commit()
        row = db.execute(
            """SELECT e.*, r.title as request_title
               FROM expenses e
               LEFT JOIN requests r ON e.request_id = r.id
               WHERE e.id = ?""",
            (cur.lastrowid,),
        ).fetchone()
        data = dict(row)
        data["attachments"] = _parse_attachments(data.get("attachments"))
        return data
    finally:
        db.close()


@router.get("")
def list_expenses(limit: int = 100):
    db = get_db()
    try:
        rows = db.execute(
            """SELECT e.*, r.title as request_title
               FROM expenses e
               LEFT JOIN requests r ON e.request_id = r.id
               WHERE e.deleted_at IS NULL
               ORDER BY e.date DESC, e.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["attachments"] = _parse_attachments(item.get("attachments"))
            result.append(item)
        return result
    finally:
        db.close()


@router.get("/stats")
def summary():
    db = get_db()
    try:
        today = date.today().isoformat()
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        pending = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE deleted_at IS NULL AND kind = 'reimbursable' AND reimbursement_status = 'pending'""",
        ).fetchone()
        reimbursed_30d = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE deleted_at IS NULL AND kind = 'reimbursable' AND reimbursement_status = 'reimbursed'
                 AND date >= ?""",
            (thirty_days_ago,),
        ).fetchone()
        private_30d = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE deleted_at IS NULL AND kind = 'private'
                 AND date >= ?""",
            (thirty_days_ago,),
        ).fetchone()
        total_30d = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE deleted_at IS NULL AND date >= ?""",
            (thirty_days_ago,),
        ).fetchone()
        recent = db.execute(
            """SELECT e.*, r.title as request_title
               FROM expenses e
               LEFT JOIN requests r ON e.request_id = r.id
               WHERE e.deleted_at IS NULL
               ORDER BY e.date DESC, e.id DESC
               LIMIT 5""",
        ).fetchall()
        return {
            "pending": {"count": pending["cnt"], "total": pending["total"]},
            "reimbursed_30d": {"count": reimbursed_30d["cnt"], "total": reimbursed_30d["total"]},
            "private_30d": {"count": private_30d["cnt"], "total": private_30d["total"]},
            "total_30d": {"count": total_30d["cnt"], "total": total_30d["total"]},
            "recent": [
                {**dict(row), "attachments": _parse_attachments(row["attachments"])}
                for row in recent
            ],
            "as_of": today,
        }
    finally:
        db.close()


@router.get("/{expense_id}")
def get_expense(expense_id: int):
    db = get_db()
    try:
        row = db.execute(
            """SELECT e.*, r.title as request_title
               FROM expenses e
               LEFT JOIN requests r ON e.request_id = r.id
               WHERE e.id = ? AND e.deleted_at IS NULL""",
            (expense_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["attachments"] = _parse_attachments(data.get("attachments"))
        return data
    finally:
        db.close()


@router.put("/{expense_id}")
async def update_expense(
    expense_id: int,
    date: str = Form(None),
    title: str = Form(None),
    amount: float = Form(None),
    currency: str = Form(None),
    vendor: str = Form(None),
    category: str = Form(None),
    kind: str = Form(None),
    reimbursement_status: str = Form(None),
    request_id: int = Form(None),
    notes: str = Form(None),
    attachments: list[UploadFile] = File(None),
):
    new_attachments = await _store_uploads(attachments)
    db = get_db()
    try:
        row = db.execute("SELECT attachments FROM expenses WHERE id = ? AND deleted_at IS NULL", (expense_id,)).fetchone()
        if not row:
            return {"ok": False}
        existing_attachments = _parse_attachments(row["attachments"])
        merged_attachments = existing_attachments + new_attachments

        fields, values = [], []
        for key, value in (
            ("date", date),
            ("title", title),
            ("amount", amount),
            ("currency", currency),
            ("vendor", vendor),
            ("category", category),
            ("kind", kind),
            ("reimbursement_status", reimbursement_status),
            ("request_id", request_id),
            ("notes", notes),
        ):
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        if new_attachments:
            fields.append("attachments = ?")
            values.append(json.dumps(merged_attachments))
        if not fields:
            return {"ok": True}
        values.append(expense_id)
        db.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
        row = db.execute(
            """SELECT e.*, r.title as request_title
               FROM expenses e
               LEFT JOIN requests r ON e.request_id = r.id
               WHERE e.id = ?""",
            (expense_id,),
        ).fetchone()
        data = dict(row)
        data["attachments"] = _parse_attachments(data.get("attachments"))
        return data
    finally:
        db.close()


@router.delete("/{expense_id}")
def delete_expense(expense_id: int):
    db = get_db()
    try:
        db.execute(
            "UPDATE expenses SET deleted_at = ? WHERE id = ?",
            (date.today().isoformat(), expense_id),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()
