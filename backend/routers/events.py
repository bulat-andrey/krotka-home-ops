from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from auth import verify_auth
from database import get_db

router = APIRouter(prefix="/api/events", dependencies=[Depends(verify_auth)])


class EventCreate(BaseModel):
    date: str
    type: Optional[str] = None
    title: str
    description: Optional[str] = None
    zone_id: Optional[int] = None
    contractor_id: Optional[int] = None


@router.post("")
def create_event(event: EventCreate):
    db = get_db()
    cur = db.execute(
        "INSERT INTO events (date, type, title, description, zone_id, contractor_id) VALUES (?, ?, ?, ?, ?, ?)",
        (event.date, event.type, event.title, event.description, event.zone_id, event.contractor_id),
    )
    db.commit()
    eid = cur.lastrowid
    db.close()
    return {"id": eid}


@router.get("")
def list_events(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    db = get_db()
    rows = db.execute(
        """
        SELECT date, type, title, description, zone_id, contractor_id FROM (
            SELECT date, 'watering' as type, 'Полив' as title,
                   notes as description, zone_id, NULL as contractor_id FROM watering_events
            UNION ALL
            SELECT date, 'mowing' as type, 'Покос' as title,
                   notes as description, NULL as zone_id, contractor_id FROM mowing_events
            UNION ALL
            SELECT sent_at as date, 'request' as type, title,
                   summary as description, NULL as zone_id, contractor_id FROM requests WHERE sent_at IS NOT NULL
            UNION ALL
            SELECT date, type, title, description, zone_id, contractor_id FROM events
        ) ORDER BY date DESC LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
