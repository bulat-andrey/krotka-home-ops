from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import verify_auth
from database import get_db

router = APIRouter(dependencies=[Depends(verify_auth)])


class ZonePayload(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    type: str | None = Field(default=None, max_length=40)
    sun_exposure: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    active: bool = True


class WateringEvent(BaseModel):
    zone_id: int
    date: str
    duration_min: Optional[int] = None
    method: Optional[str] = None
    notes: Optional[str] = None


@router.get("/api/zones")
def list_zones():
    conn = get_db()
    rows = conn.execute(
        """SELECT id, code, name, type, sun_exposure, notes, active
           FROM zones WHERE active = 1
           ORDER BY COALESCE(code, name), name"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/zones", status_code=201)
def create_zone(zone: ZonePayload):
    conn = get_db()
    code = zone.code.strip().upper() if zone.code else None
    try:
        cur = conn.execute(
            """INSERT INTO zones (code, name, type, sun_exposure, notes, active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                code,
                zone.name.strip(),
                zone.type,
                zone.sun_exposure,
                zone.notes,
                1 if zone.active else 0,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM zones WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Zone code or name already exists") from exc
        raise
    finally:
        conn.close()


@router.put("/api/zones/{zone_id}")
def update_zone(zone_id: int, zone: ZonePayload):
    conn = get_db()
    code = zone.code.strip().upper() if zone.code else None
    try:
        conn.execute(
            """UPDATE zones
               SET code = ?, name = ?, type = ?, sun_exposure = ?, notes = ?, active = ?
               WHERE id = ?""",
            (
                code,
                zone.name.strip(),
                zone.type,
                zone.sun_exposure,
                zone.notes,
                1 if zone.active else 0,
                zone_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Zone not found")
        return dict(row)
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Zone code or name already exists") from exc
        raise
    finally:
        conn.close()


@router.delete("/api/zones/{zone_id}")
def deactivate_zone(zone_id: int):
    conn = get_db()
    try:
        cur = conn.execute("UPDATE zones SET active = 0 WHERE id = ?", (zone_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Zone not found")
        return {"ok": True}
    finally:
        conn.close()


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


# IMPORTANT: Place /last BEFORE /{id} to avoid route conflict
@router.get("/api/watering/last")
def last_watering_per_zone():
    conn = get_db()
    rows = conn.execute("""
        SELECT z.id as zone_id, z.code, z.name, w.date, w.duration_min, w.method
        FROM zones z
        LEFT JOIN watering_events w ON w.id = (
            SELECT id FROM watering_events WHERE zone_id = z.id ORDER BY date DESC LIMIT 1
        )
        WHERE z.active = 1
        ORDER BY COALESCE(z.code, z.name), z.name
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


@router.get("/api/watering/{watering_id}")
def get_watering(watering_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM watering_events WHERE id = ?", (watering_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Watering event not found")
    return dict(row)


@router.put("/api/watering/{watering_id}")
def update_watering(watering_id: int, event: WateringEvent):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE watering_events SET zone_id = ?, date = ?, duration_min = ?, method = ?, notes = ? WHERE id = ?",
            (event.zone_id, event.date, event.duration_min, event.method, event.notes, watering_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM watering_events WHERE id = ?", (watering_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Watering event not found")
        return dict(row)
    finally:
        conn.close()


@router.delete("/api/watering/{watering_id}")
def delete_watering(watering_id: int):
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM watering_events WHERE id = ?", (watering_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Watering event not found")
        return {"ok": True}
    finally:
        conn.close()
