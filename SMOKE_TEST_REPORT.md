# Smoke Test Report

**Date**: 2026-06-29T17:22 UTC
**Docker**: 25.0.14 (build), 25.0.16 (daemon)
**Image**: python:3.12-slim based, built from backend/Dockerfile
**Method**: docker build + docker run (docker compose plugin not available on host; equivalent invocation with -v and --env-file flags)

## Build

```
docker build -t krotka-homeops-test ./backend
```

**Result**: SUCCESS (all 6 layers cached/built, image sha256:68abd2d8...)

## Smoke Tests

| # | Endpoint | Method | Auth | HTTP Code | Result |
|---|----------|--------|------|-----------|--------|
| 1 | /api/health | GET | None | 200 | PASS |
| 2 | /api/dashboard | GET | Basic | 200 | PASS |
| 3 | /api/watering | POST | Basic | 200 | PASS |
| 4 | /api/recommendations | GET | Basic | 200 | PASS |
| 5 | /api/mowing | POST | Basic | 200 | PASS |
| 6 | /api/requests | POST | Basic | 201 | PASS |
| 7 | /api/emails | POST | Basic | 200 | PASS |
| 8 | /api/events | GET | Basic | 200 | PASS |

## Response Verification

- **/api/health**: `{"status":"ok"}`
- **/api/dashboard**: JSON with keys: recommendations, last_watering, last_mowing, open_requests, overdue_responses
- **/api/recommendations**: 5 zones with per-zone statuses (Можно подождать / Полить сегодня)
- **/api/events**: Unified feed with watering + mowing events aggregated

## Overall: ALL PASS (8/8)
