from datetime import date, timedelta

from database import get_db

STATUS_WATER = "Полить сегодня"
STATUS_SKIP = "Не поливать, ожидается дождь"
STATUS_WAIT = "Можно подождать"


def generate_recommendations():
    """Generate per-zone watering recommendations based on weather and last watering."""
    conn = get_db()
    today = date.today()
    today_str = today.isoformat()
    two_days_ago = (today - timedelta(days=2)).isoformat()

    # Get weather context
    weather = conn.execute(
        "SELECT temp_max, rain_mm, forecast_rain_mm FROM weather_daily WHERE date = ?",
        (today_str,),
    ).fetchone()

    # Rain in last 48h
    rain_rows = conn.execute(
        "SELECT COALESCE(SUM(rain_mm), 0) as total FROM weather_daily WHERE date >= ?",
        (two_days_ago,),
    ).fetchone()
    rain_48h = rain_rows["total"] if rain_rows else 0

    temp_max = weather["temp_max"] if weather else None
    forecast_rain = weather["forecast_rain_mm"] if weather else 0

    zones = conn.execute("SELECT id, name, type FROM zones").fetchall()

    # Clear today's old recommendations
    conn.execute("DELETE FROM recommendations WHERE date = ?", (today_str,))

    for zone in zones:
        zone_id = zone["id"]
        zone_type = zone["type"]

        # Last watering for this zone
        last = conn.execute(
            "SELECT date FROM watering_events WHERE zone_id = ? ORDER BY date DESC LIMIT 1",
            (zone_id,),
        ).fetchone()
        days_since = (today - date.fromisoformat(last["date"])).days if last else 999

        status, reason = _decide(zone_type, temp_max, rain_48h, forecast_rain, days_since)

        conn.execute(
            "INSERT INTO recommendations (zone_id, date, status, reason) VALUES (?, ?, ?, ?)",
            (zone_id, today_str, status, reason),
        )

    conn.commit()
    conn.close()


def _decide(zone_type, temp_max, rain_48h, forecast_rain, days_since):
    heat = (temp_max or 0) > 28
    heavy_rain = (forecast_rain or 0) > 5

    if zone_type == "lawn":
        if heavy_rain:
            return STATUS_SKIP, "Ожидается сильный дождь"
        if heat and rain_48h < 1 and days_since >= 2:
            return STATUS_WATER, "Жара >28°C, нет дождя 2 дня"
        return STATUS_WAIT, None

    if zone_type == "bushes":
        # Самшиты: deep infrequent, skip if watered <3d ago
        if days_since < 3:
            return STATUS_WAIT, "Глубокий редкий полив, <3 дней назад"
        if heavy_rain:
            return STATUS_SKIP, "Ожидается дождь"
        if heat and days_since >= 3:
            return STATUS_WATER, "Жара, давно не поливали"
        return STATUS_WAIT, None

    if zone_type == "new_plants":
        if heavy_rain:
            return STATUS_SKIP, "Ожидается дождь"
        if heat and days_since >= 1:
            return STATUS_WATER, "Жара, новые посадки требуют внимания"
        if days_since >= 2:
            return STATUS_WATER, "Не поливали 2+ дня"
        return STATUS_WAIT, None

    # shade_area / sun_area / default
    if heavy_rain:
        return STATUS_SKIP, "Ожидается дождь"
    if zone_type == "sun_area" and heat and days_since >= 2:
        return STATUS_WATER, "Солнечная зона, жара, нет полива 2+ дня"
    if heat and rain_48h < 1 and days_since >= 2:
        return STATUS_WATER, "Жара >28°C, нет дождя"
    return STATUS_WAIT, None
