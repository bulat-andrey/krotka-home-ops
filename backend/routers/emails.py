import json
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api/emails", dependencies=[Depends(verify_auth)])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")


@router.post("")
async def save_email(
    request_id: int = Form(None),
    direction: str = Form(...),
    sender: str = Form(None),
    recipient: str = Form(None),
    subject: str = Form(None),
    body: str = Form(None),
    sent_at: str = Form(None),
    attachments: list[UploadFile] = File(None),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    attachment_paths = []
    if attachments:
        for f in attachments:
            if f.filename:
                ext = os.path.splitext(f.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                path = os.path.join(UPLOAD_DIR, filename)
                with open(path, "wb") as out:
                    out.write(await f.read())
                attachment_paths.append(filename)

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO emails (request_id, direction, sender, recipient, subject, body, sent_at, attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, direction, sender, recipient, subject, body, sent_at, json.dumps(attachment_paths) if attachment_paths else None),
        )
        db.commit()
        return {"id": cur.lastrowid}
    finally:
        db.close()


@router.get("")
def list_emails(request_id: int = None):
    db = get_db()
    try:
        if request_id is not None:
            rows = db.execute("SELECT * FROM emails WHERE request_id = ? ORDER BY sent_at DESC", (request_id,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM emails ORDER BY sent_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
