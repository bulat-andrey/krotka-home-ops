from datetime import datetime

from fastapi import APIRouter, Depends

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api/workitems", dependencies=[Depends(verify_auth)])


@router.get("")
def list_workitems(status: str | None = None):
    db = get_db()
    try:
        sql = """
            SELECT w.*,
                   (SELECT COUNT(*) FROM requests r WHERE r.work_item_id = w.id AND r.deleted_at IS NULL) AS request_count,
                   (SELECT COUNT(*) FROM expenses e WHERE e.work_item_id = w.id AND e.deleted_at IS NULL) AS expense_count
            FROM work_items w
            WHERE w.deleted_at IS NULL
        """
        params = []
        if status:
            sql += " AND w.status = ?"
            params.append(status)
        sql += " ORDER BY CASE w.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, COALESCE(w.target_date, '9999-12-31'), w.id DESC"
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.post("", status_code=201)
def create_workitem(data: dict):
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO work_items
               (title, category, status, priority, target_date, estimated_cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"],
                data.get("category"),
                data.get("status", "idea"),
                data.get("priority", "medium"),
                data.get("target_date"),
                data.get("estimated_cost"),
                data.get("notes"),
            ),
        )
        db.commit()
        row = db.execute(
            """SELECT w.*,
                      (SELECT COUNT(*) FROM requests r WHERE r.work_item_id = w.id AND r.deleted_at IS NULL) AS request_count,
                      (SELECT COUNT(*) FROM expenses e WHERE e.work_item_id = w.id AND e.deleted_at IS NULL) AS expense_count
               FROM work_items w
               WHERE w.id = ?""",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)
    finally:
        db.close()


@router.put("/{workitem_id}")
def update_workitem(workitem_id: int, data: dict):
    db = get_db()
    try:
        fields, values = [], []
        for key in ("title", "category", "status", "priority", "target_date", "estimated_cost", "notes"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return {"ok": True}
        fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat(timespec="seconds"))
        values.append(workitem_id)
        db.execute(f"UPDATE work_items SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
        row = db.execute(
            """SELECT w.*,
                      (SELECT COUNT(*) FROM requests r WHERE r.work_item_id = w.id AND r.deleted_at IS NULL) AS request_count,
                      (SELECT COUNT(*) FROM expenses e WHERE e.work_item_id = w.id AND e.deleted_at IS NULL) AS expense_count
               FROM work_items w
               WHERE w.id = ?""",
            (workitem_id,),
        ).fetchone()
        return dict(row)
    finally:
        db.close()


@router.delete("/{workitem_id}")
def delete_workitem(workitem_id: int):
    db = get_db()
    try:
        db.execute(
            "UPDATE work_items SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), datetime.utcnow().isoformat(timespec="seconds"), workitem_id),
        )
        db.commit()
        return {"ok": True}
    finally:
        db.close()
