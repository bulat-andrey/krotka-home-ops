from datetime import date, datetime

from fastapi import APIRouter, Depends

from auth import verify_auth
from database import get_db

router = APIRouter(dependencies=[Depends(verify_auth)])


@router.get("/api/dashboard")
def dashboard():
    db = get_db()
    today = date.today()
    today_str = today.isoformat()

    # Recommendations: today's per zone
    recs = db.execute(
        """SELECT r.status, r.reason, z.name as zone_name
           FROM recommendations r JOIN zones z ON r.zone_id = z.id
           WHERE r.date = ?""",
        (today_str,),
    ).fetchall()
    recommendations = [dict(r) for r in recs]

    # Last watering per zone with days_since
    watering_rows = db.execute("""
        SELECT z.id, z.name, w.date
        FROM zones z
        LEFT JOIN watering_events w ON w.id = (
            SELECT id FROM watering_events WHERE zone_id = z.id ORDER BY date DESC LIMIT 1
        )
    """).fetchall()
    last_watering = []
    for r in watering_rows:
        d = {"zone_id": r["id"], "zone_name": r["name"], "date": r["date"]}
        if r["date"]:
            d["days_since"] = (today - date.fromisoformat(r["date"])).days
        else:
            d["days_since"] = None
        last_watering.append(d)

    # Last mowing + overdue flag (>10 days)
    mow = db.execute(
        "SELECT date FROM mowing_events ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if mow:
        last_mow_date = datetime.strptime(mow["date"], "%Y-%m-%d").date()
        days_since_mow = (today - last_mow_date).days
        last_mowing = {"date": mow["date"], "days_since": days_since_mow, "overdue": days_since_mow > 10}
    else:
        last_mowing = {"date": None, "days_since": None, "overdue": True}

    # Open requests count
    open_count = db.execute(
        "SELECT COUNT(*) as cnt FROM requests WHERE status NOT IN ('closed', 'answered')"
    ).fetchone()["cnt"]

    # Overdue responses
    overdue = db.execute(
        """SELECT title FROM requests
           WHERE due_at < ? AND status NOT IN ('closed', 'answered')
           ORDER BY due_at""",
        (today_str,),
    ).fetchall()
    overdue_responses = [r["title"] for r in overdue]

    db.close()
    return {
        "recommendations": recommendations,
        "last_watering": last_watering,
        "last_mowing": last_mowing,
        "open_requests": open_count,
        "overdue_responses": overdue_responses,
    }
