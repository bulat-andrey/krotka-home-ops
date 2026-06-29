from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth import verify_auth
from database import get_db

router = APIRouter(dependencies=[Depends(verify_auth)])


@router.get("/api/zones")
def list_zones():
    conn = get_db()
    rows = conn.execute("SELECT id, name, type, sun_exposure FROM zones").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/watering")
def log_watering(event: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO watering_events (zone_id, date, duration_min, method, notes) VALUES (?, ?, ?, ?, ?)",
        (
            event["zone_id"],
            event.get("date", date.today().isoformat()),
            event.get("duration_minutes"),
            event.get("method"),
            event.get("notes"),
        ),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/watering")
def watering_history(zone_id: Optional[int] = Query(None)):
    conn = get_db()
    if zone_id:
        rows = conn.execute(
            "SELECT * FROM watering_events WHERE zone_id = ? ORDER BY date DESC", (zone_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM watering_events ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/watering/last")
def last_watering_per_zone():
    conn = get_db()
    rows = conn.execute("""
        SELECT z.id as zone_id, z.name, w.date, w.duration_min, w.method
        FROM zones z
        LEFT JOIN watering_events w ON w.id = (
            SELECT id FROM watering_events WHERE zone_id = z.id ORDER BY date DESC LIMIT 1
        )
    """).fetchall()
    conn.close()
    today = date.today()
    result = []
    for r in rows:
        d = dict(r)
        if d["date"]:
            last = date.fromisoformat(d["date"])
            d["days_since"] = (today - last).days
        else:
            d["days_since"] = None
        result.append(d)
    return result
