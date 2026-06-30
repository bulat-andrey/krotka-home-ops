from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api", dependencies=[Depends(verify_auth)])


@router.get("/contractors")
def list_contractors():
    db = get_db()
    rows = db.execute("SELECT id, name FROM contractors ORDER BY name").fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("/requests", status_code=201)
def create_request(data: dict):
    db = get_db()
    cur = db.execute(
        """INSERT INTO requests (title, contractor_id, work_item_id, status, due_at, summary, next_action)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["title"],
            data.get("contractor_id"),
            data.get("work_item_id"),
            data.get("status", "draft"),
            data.get("due_at"),
            data.get("summary"),
            data.get("next_action"),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM requests WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.close()
    return dict(row)


@router.get("/requests")
def list_requests(status: str | None = None, contractor: int | None = Query(None)):
    db = get_db()
    sql = """SELECT r.*, c.name as contractor_name, w.title as work_item_title
             FROM requests r
             LEFT JOIN contractors c ON r.contractor_id = c.id
             LEFT JOIN work_items w ON r.work_item_id = w.id
             WHERE r.deleted_at IS NULL"""
    params = []
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if contractor:
        sql += " AND r.contractor_id = ?"
        params.append(contractor)
    sql += " ORDER BY r.id DESC"
    rows = db.execute(sql, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.put("/requests/{request_id}")
def update_request(request_id: int, data: dict):
    db = get_db()
    fields, values = [], []
    for key in ("title", "contractor_id", "work_item_id", "status", "sent_at", "due_at", "last_response_at", "summary", "next_action"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return {"ok": True}
    values.append(request_id)
    db.execute(f"UPDATE requests SET {', '.join(fields)} WHERE id = ?", values)
    db.commit()
    row = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    db.close()
    return dict(row)


@router.delete("/requests/{request_id}")
def delete_request(request_id: int):
    db = get_db()
    db.execute(
        "UPDATE requests SET deleted_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(timespec="seconds"), request_id),
    )
    db.commit()
    db.close()
    return {"ok": True}


@router.get("/requests/overdue")
def overdue_requests():
    db = get_db()
    today = date_type.today().isoformat()
    rows = db.execute(
        """SELECT r.*, c.name as contractor_name FROM requests r
           LEFT JOIN contractors c ON r.contractor_id = c.id
           WHERE r.deleted_at IS NULL AND r.due_at < ? AND r.status NOT IN ('closed', 'answered')
           ORDER BY r.due_at""",
        (today,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
