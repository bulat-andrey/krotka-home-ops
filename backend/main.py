import asyncio
import os
import secrets
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import AUTH_PASSWORD, verify_auth
from database import init_db
from weather import fetch_weather
from recommendations import generate_recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    async def fetch_and_recommend():
        await fetch_weather()
        generate_recommendations()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(fetch_and_recommend, "cron", hour=6, minute=0)
    scheduler.start()
    # Run initial fetch on startup
    asyncio.create_task(fetch_and_recommend())
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    if not secrets.compare_digest(body.get("password", ""), AUTH_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    response = JSONResponse({"ok": True})
    response.set_cookie("session", AUTH_PASSWORD, httponly=True, samesite="strict")
    return response


# Register routers
from routers.mowing import router as mowing_router  # noqa: E402
from routers.requests import router as requests_router  # noqa: E402
from routers.emails import router as emails_router  # noqa: E402
from routers.watering import router as watering_router  # noqa: E402
from routers.events import router as events_router  # noqa: E402
from routers.recommendations import router as recommendations_router  # noqa: E402
from routers.dashboard import router as dashboard_router  # noqa: E402

app.include_router(mowing_router)
app.include_router(requests_router)
app.include_router(emails_router)
app.include_router(watering_router)
app.include_router(events_router)
app.include_router(recommendations_router)
app.include_router(dashboard_router)

# Mount frontend static files (after API routes so /api/* takes priority)
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
