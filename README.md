# Krotka Home Ops

Small FastAPI application for tracking home operations: watering, mowing, contractor requests, email records, events, weather, and garden recommendations.

## Run locally

```sh
cp .env.example .env
docker compose up -d --build
```

By default the app listens on `http://localhost:8010`, leaving `8000` free for other local services. It binds to `127.0.0.1`; set `HOST_BIND=0.0.0.0` only if you intentionally want direct network access.

Set `AUTH_PASSWORD` in `.env` before exposing the app beyond local development.
The first admin account is seeded as `admin` using `AUTH_PASSWORD`.

On the current host, Caddy publishes Home Ops at:

```text
https://home.46.225.65.120.sslip.io
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `HOST_PORT` | `8010` | Host port published by Docker Compose |
| `HOST_BIND` | `127.0.0.1` | Host interface published by Docker Compose |
| `ADMIN_USERNAME` | `admin` | Username for the first seeded admin account |
| `AUTH_PASSWORD` | required | Password used by the web app |
| `DB_PATH` | `/data/krotka.db` | SQLite database path inside the container |
| `LATITUDE` | `54.5189` | Weather lookup latitude |
| `LONGITUDE` | `18.5305` | Weather lookup longitude |
| `WEATHER_PAST_DAYS` | `30` | Number of past weather days to keep refreshing |
| `WEATHER_FORECAST_DAYS` | `5` | Number of forecast days to fetch |
