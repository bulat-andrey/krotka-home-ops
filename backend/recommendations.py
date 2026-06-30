from datetime import date, timedelta

from database import get_db

STATUS_WATER = "Полить сегодня"
STATUS_SKIP = "Не поливать, ожидается дождь"
STATUS_WAIT = "Можно подождать"

ZONE_RULES = {
    "lawn": {"dry_after": 4, "hot_dry_after": 2, "recent_rain_ok": 8, "forecast_skip": 5},
    "sun_area": {"dry_after": 3, "hot_dry_after": 2, "recent_rain_ok": 6, "forecast_skip": 5},
    "new_plants": {"dry_after": 2, "hot_dry_after": 1, "recent_rain_ok": 4, "forecast_skip": 4},
    "bushes": {"dry_after": 7, "hot_dry_after": 4, "recent_rain_ok": 10, "forecast_skip": 8},
    "hedge": {"dry_after": 7, "hot_dry_after": 4, "recent_rain_ok": 10, "forecast_skip": 8},
    "tree": {"dry_after": 10, "hot_dry_after": 5, "recent_rain_ok": 12, "forecast_skip": 10},
    "shade_area": {"dry_after": 8, "hot_dry_after": 6, "recent_rain_ok": 10, "forecast_skip": 8},
    "other": {"dry_after": 5, "hot_dry_after": 3, "recent_rain_ok": 8, "forecast_skip": 5},
}


def generate_recommendations():
    """Generate per-zone watering recommendations based on weather and last watering."""
    conn = get_db()
    today = date.today()
    today_str = today.isoformat()

    weather = conn.execute(
        "SELECT temp_max, rain_mm FROM weather_daily WHERE date = ?",
        (today_str,),
    ).fetchone()
    temp_max = weather["temp_max"] if weather else None
    forecast_today = weather["rain_mm"] if weather else 0
    yesterday = today - timedelta(days=1)
    rain_3d = _rain_sum(conn, today - timedelta(days=3), yesterday)
    rain_7d = _rain_sum(conn, today - timedelta(days=7), yesterday)
    forecast_48h = (forecast_today or 0) + _rain_sum(
        conn, today + timedelta(days=1), today + timedelta(days=1)
    )

    zones = conn.execute(
        "SELECT id, name, type, sun_exposure FROM zones WHERE active = 1"
    ).fetchall()

    conn.execute("DELETE FROM recommendations WHERE date = ?", (today_str,))

    for zone in zones:
        zone_id = zone["id"]
        zone_type = zone["type"]

        # Last watering for this zone
        last = conn.execute(
            "SELECT date FROM watering_events WHERE zone_id = ? ORDER BY date DESC LIMIT 1",
            (zone_id,),
        ).fetchone()
        days_since = (today - date.fromisoformat(last["date"])).days if last else None

        status, reason = _decide(
            zone_type=zone_type,
            sun_exposure=zone["sun_exposure"],
            temp_max=temp_max,
            rain_3d=rain_3d,
            rain_7d=rain_7d,
            forecast_today=forecast_today or 0,
            forecast_48h=forecast_48h,
            days_since=days_since,
        )

        conn.execute(
            "INSERT INTO recommendations (zone_id, date, status, reason) VALUES (?, ?, ?, ?)",
            (zone_id, today_str, status, reason),
        )

    conn.commit()
    conn.close()


def _rain_sum(conn, start: date, end: date) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(rain_mm), 0) as total
           FROM weather_daily
           WHERE date >= ? AND date <= ?""",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return float(row["total"] or 0)


def _adjust_rules_for_exposure(rules: dict, sun_exposure: str | None) -> dict:
    adjusted = dict(rules)
    if sun_exposure == "sun":
        adjusted["dry_after"] = max(1, adjusted["dry_after"] - 1)
    elif sun_exposure == "shade":
        adjusted["dry_after"] += 2
        adjusted["hot_dry_after"] += 1
    return adjusted


def _decide(
    zone_type,
    sun_exposure,
    temp_max,
    rain_3d,
    rain_7d,
    forecast_today,
    forecast_48h,
    days_since,
):
    rules = _adjust_rules_for_exposure(
        ZONE_RULES.get(zone_type) or ZONE_RULES["other"], sun_exposure
    )
    heat = (temp_max or 0) >= 28
    dry_after = rules["hot_dry_after"] if heat else rules["dry_after"]
    effective_days_since = days_since if days_since is not None else 999
    last_water_text = "полив не записан" if days_since is None else f"полив {days_since} дн. назад"
    weather_text = (
        f"дождь 3д {rain_3d:.1f} мм, 7д {rain_7d:.1f} мм, "
        f"прогноз сегодня {forecast_today:.1f} мм, 48ч {forecast_48h:.1f} мм"
    )

    if forecast_48h >= rules["forecast_skip"]:
        return (
            STATUS_SKIP,
            f"{weather_text}; {last_water_text}; порог зоны {rules['forecast_skip']} мм",
        )

    if rain_3d >= rules["recent_rain_ok"]:
        return STATUS_WAIT, f"за последние 3 дня было {rain_3d:.1f} мм дождя; {last_water_text}"

    if effective_days_since < dry_after:
        return (
            STATUS_WAIT,
            f"{last_water_text}; порог для зоны сейчас {dry_after} дн.; {weather_text}",
        )

    if forecast_48h >= 2 and effective_days_since <= dry_after + 1:
        return (
            STATUS_WAIT,
            f"зона близко к поливу, но в ближайшие 2 дня прогноз {forecast_48h:.1f} мм; {last_water_text}",
        )

    if heat and rain_7d < rules["recent_rain_ok"]:
        return (
            STATUS_WATER,
            f"жара до {temp_max:.0f}°C, {last_water_text}, за 7 дней только {rain_7d:.1f} мм",
        )

    return (
        STATUS_WATER,
        f"{last_water_text}; дождя за 3 дня {rain_3d:.1f} мм, значимого дождя в прогнозе нет",
    )
