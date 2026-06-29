# Krotka Home Ops

Small FastAPI application for tracking home operations: watering, mowing, contractor requests, email records, events, weather, and garden recommendations.

## Run locally

```sh
cp .env.example .env
docker compose up -d --build
```

By default the app listens on `http://localhost:8010`, leaving `8000` free for other local services.

Set `AUTH_PASSWORD` in `.env` before exposing the app beyond local development.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `HOST_PORT` | `8010` | Host port published by Docker Compose |
| `AUTH_PASSWORD` | `changeme` | Password used by the web app |
| `DB_PATH` | `/data/krotka.db` | SQLite database path inside the container |
| `LATITUDE` | `52.2297` | Weather lookup latitude |
| `LONGITUDE` | `21.0122` | Weather lookup longitude |

