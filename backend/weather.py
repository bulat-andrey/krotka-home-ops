import json
import os
from datetime import date, timedelta

import httpx

from database import get_db

LATITUDE = os.environ.get("LATITUDE", "52.2297")
LONGITUDE = os.environ.get("LONGITUDE", "21.0122")
WEATHER_PAST_DAYS = int(os.environ.get("WEATHER_PAST_DAYS", "30"))
WEATHER_FORECAST_DAYS = int(os.environ.get("WEATHER_FORECAST_DAYS", "5"))
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_weather():
    """Fetch daily weather from Open-Meteo and store in weather_daily table."""
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "past_days": WEATHER_PAST_DAYS,
        "forecast_days": WEATHER_FORECAST_DAYS,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
    data = resp.json()
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    today = date.today().isoformat()
    # forecast rain = sum of precipitation for days after today
    forecast_rain = sum(
        precip[i] or 0 for i, d in enumerate(dates) if d > today
    )

    conn = get_db()
    for i, d in enumerate(dates):
        conn.execute(
            """INSERT OR REPLACE INTO weather_daily
               (date, temp_max, temp_min, rain_mm, forecast_rain_mm, raw_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                d,
                temp_max[i] if i < len(temp_max) else None,
                temp_min[i] if i < len(temp_min) else None,
                precip[i] if i < len(precip) else None,
                forecast_rain if d == today else None,
                json.dumps(data),
            ),
        )
    conn.commit()
    conn.close()


def get_latest_weather() -> dict:
    """Return the most recent weather data."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM weather_daily ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {}
    return dict(row)
