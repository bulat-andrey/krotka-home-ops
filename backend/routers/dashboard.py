from datetime import date, datetime, timedelta
import os

from fastapi import APIRouter, Depends

from auth import verify_auth
from database import get_db

router = APIRouter(dependencies=[Depends(verify_auth)])

MOWING_INTERVAL_DAYS = 21
MOWING_REQUEST_LEAD_DAYS = 4
WIND_THRESHOLD_KT = float(os.environ.get("WIND_THRESHOLD_KT", "14"))


@router.get("/api/dashboard")
def dashboard():
    db = get_db()
    today = date.today()
    today_str = today.isoformat()

    # Recommendations: today's per zone
    recs = db.execute(
        """SELECT r.status, r.reason, z.code as zone_code, z.name as zone_name
           FROM recommendations r JOIN zones z ON r.zone_id = z.id
           WHERE r.date = ? AND z.active = 1""",
        (today_str,),
    ).fetchall()
    recommendations = [dict(r) for r in recs]

    # Last watering per zone with days_since
    watering_rows = db.execute("""
        SELECT z.id, z.code, z.name, w.date
        FROM zones z
        LEFT JOIN watering_events w ON w.id = (
            SELECT id FROM watering_events WHERE zone_id = z.id ORDER BY date DESC LIMIT 1
        )
        WHERE z.active = 1
        ORDER BY COALESCE(z.code, z.name), z.name
    """).fetchall()
    last_watering = []
    for r in watering_rows:
        d = {"zone_id": r["id"], "zone_code": r["code"], "zone_name": r["name"], "date": r["date"]}
        if r["date"]:
            d["days_since"] = (today - date.fromisoformat(r["date"])).days
        else:
            d["days_since"] = None
        last_watering.append(d)

    # Last mowing + next planned mowing by contract cycle.
    mow = db.execute(
        "SELECT date FROM mowing_events ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if mow:
        last_mow_date = datetime.strptime(mow["date"], "%Y-%m-%d").date()
        days_since_mow = (today - last_mow_date).days
        next_mow_date = last_mow_date + timedelta(days=MOWING_INTERVAL_DAYS)
        request_from_date = next_mow_date - timedelta(days=MOWING_REQUEST_LEAD_DAYS)
        last_mowing = {
            "date": mow["date"],
            "days_since": days_since_mow,
            "next_date": next_mow_date.isoformat(),
            "days_until_next": (next_mow_date - today).days,
            "request_from": request_from_date.isoformat(),
            "days_until_request": (request_from_date - today).days,
            "request_due": today >= request_from_date,
            "overdue": today > next_mow_date,
            "interval_days": MOWING_INTERVAL_DAYS,
            "request_lead_days": MOWING_REQUEST_LEAD_DAYS,
        }
    else:
        last_mowing = {
            "date": None,
            "days_since": None,
            "next_date": None,
            "days_until_next": None,
            "request_from": None,
            "days_until_request": None,
            "request_due": True,
            "overdue": True,
            "interval_days": MOWING_INTERVAL_DAYS,
            "request_lead_days": MOWING_REQUEST_LEAD_DAYS,
        }

    # Open requests count
    open_count = db.execute(
        "SELECT COUNT(*) as cnt FROM requests WHERE status NOT IN ('closed', 'answered') AND deleted_at IS NULL"
    ).fetchone()["cnt"]

    # Overdue responses
    overdue = db.execute(
        """SELECT title FROM requests
           WHERE due_at < ? AND status NOT IN ('closed', 'answered') AND deleted_at IS NULL
           ORDER BY due_at""",
        (today_str,),
    ).fetchall()
    overdue_responses = [r["title"] for r in overdue]

    weather_forecast = db.execute(
        """SELECT date, temp_max, temp_min, rain_mm
           FROM weather_daily
           WHERE date >= ?
           ORDER BY date
           LIMIT 5""",
        (today_str,),
    ).fetchall()

    rain_history = db.execute(
        """SELECT date, rain_mm
           FROM weather_daily
           WHERE date < ?
           ORDER BY date DESC
           LIMIT 14""",
        (today_str,),
    ).fetchall()
    rain_7d = db.execute(
        """SELECT COALESCE(SUM(rain_mm), 0) as total
           FROM weather_daily
           WHERE date < ? AND date >= ?""",
        (today_str, (today - timedelta(days=7)).isoformat()),
    ).fetchone()["total"]
    rain_30d = db.execute(
        """SELECT COALESCE(SUM(rain_mm), 0) as total
           FROM weather_daily
           WHERE date < ? AND date >= ?""",
        (today_str, (today - timedelta(days=30)).isoformat()),
    ).fetchone()["total"]

    wind_start_30d = (today - timedelta(days=30)).isoformat()
    wind_history = db.execute(
        """SELECT date,
                  MAX(wind_speed_kt) as max_wind_kt,
                  SUM(CASE WHEN wind_speed_kt >= ? THEN 1 ELSE 0 END) as hours_over_threshold
           FROM wind_hourly
           WHERE date < ? AND date >= ?
           GROUP BY date
           ORDER BY date DESC
           LIMIT 14""",
        (WIND_THRESHOLD_KT, today_str, wind_start_30d),
    ).fetchall()
    windy_days_30d = db.execute(
        """SELECT COUNT(*) as cnt FROM (
               SELECT date
               FROM wind_hourly
               WHERE date < ? AND date >= ?
               GROUP BY date
               HAVING MAX(wind_speed_kt) >= ?
           )""",
        (today_str, wind_start_30d, WIND_THRESHOLD_KT),
    ).fetchone()["cnt"]
    wind_forecast = db.execute(
        """SELECT date,
                  MAX(wind_speed_kt) as max_wind_kt,
                  SUM(CASE WHEN wind_speed_kt >= ? THEN 1 ELSE 0 END) as hours_over_threshold
           FROM wind_hourly
           WHERE date >= ?
           GROUP BY date
           ORDER BY date
           LIMIT 5""",
        (WIND_THRESHOLD_KT, today_str),
    ).fetchall()

    db.close()
    return {
        "recommendations": recommendations,
        "last_watering": last_watering,
        "last_mowing": last_mowing,
        "weather_forecast": [dict(r) for r in weather_forecast],
        "rain_history": [dict(r) for r in rain_history],
        "rain_totals": {"last_7_days": rain_7d, "last_30_days": rain_30d},
        "wind": {
            "threshold_kt": WIND_THRESHOLD_KT,
            "windy_days_30d": windy_days_30d,
            "history": [dict(r) for r in wind_history],
            "forecast": [dict(r) for r in wind_forecast],
        },
        "open_requests": open_count,
        "overdue_responses": overdue_responses,
    }
