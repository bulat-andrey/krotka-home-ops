import os
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api/mowing", dependencies=[Depends(verify_auth)])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")


@router.post("")
async def log_mowing(
    date: str = Form(...),
    contractor_id: int = Form(None),
    quality: int = Form(None),
    notes: str = Form(None),
    photos: list[UploadFile] = File(None),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    photo_paths = []
    if photos:
        for photo in photos:
            if photo.filename:
                ext = os.path.splitext(photo.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(UPLOAD_DIR, filename)
                with open(path, "wb") as f:
                    f.write(await photo.read())
                photo_paths.append(filename)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO mowing_events (date, contractor_id, quality, notes, photos) VALUES (?, ?, ?, ?, ?)",
            (date, contractor_id, quality, notes, ",".join(photo_paths) if photo_paths else None),
        )
        db.commit()
        return {"id": cur.lastrowid}
    finally:
        db.close()


@router.get("")
def list_mowing():
    db = get_db()
    try:
        rows = db.execute(
            "SELECT m.*, c.name as contractor_name FROM mowing_events m LEFT JOIN contractors c ON m.contractor_id = c.id ORDER BY m.date DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.get("/last")
def last_mowing():
    db = get_db()
    try:
        row = db.execute(
            "SELECT m.*, c.name as contractor_name FROM mowing_events m LEFT JOIN contractors c ON m.contractor_id = c.id ORDER BY m.date DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"last_mowing": None, "days_since": None, "overdue": True}
        last_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        days_since = (date.today() - last_date).days
        return {
            "last_mowing": dict(row),
            "days_since": days_since,
            "overdue": days_since > 10,
        }
    finally:
        db.close()
