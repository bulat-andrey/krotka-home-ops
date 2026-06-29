from datetime import date

from fastapi import APIRouter, Depends

from auth import verify_auth
from database import get_db

router = APIRouter(dependencies=[Depends(verify_auth)])


@router.get("/api/recommendations")
def get_recommendations():
    conn = get_db()
    rows = conn.execute(
        """SELECT r.zone_id, z.name as zone_name, r.status, r.reason
           FROM recommendations r
           JOIN zones z ON z.id = r.zone_id
           WHERE r.date = ?
           ORDER BY z.id""",
        (date.today().isoformat(),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
