import asyncio
import os
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import authenticate_user, ensure_default_admin_user
from database import init_db
from recommendations import generate_recommendations
from weather import fetch_weather

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_admin_user()

    async def fetch_and_recommend():
        await fetch_weather()
        generate_recommendations()

    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Warsaw"))
    scheduler.add_job(fetch_and_recommend, "cron", hour="6,18", minute=0)
    scheduler.start()
    # Run initial fetch on startup
    asyncio.create_task(fetch_and_recommend())
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def disable_browser_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "admin")
    password = body.get("password", "")
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid password")
    return JSONResponse({"ok": True, "user": user})


# Register routers
from routers.mowing import router as mowing_router  # noqa: E402
from routers.requests import router as requests_router  # noqa: E402
from routers.emails import router as emails_router  # noqa: E402
from routers.watering import router as watering_router  # noqa: E402
from routers.events import router as events_router  # noqa: E402
from routers.recommendations import router as recommendations_router  # noqa: E402
from routers.dashboard import router as dashboard_router  # noqa: E402
from routers.users import router as users_router  # noqa: E402
from routers.finance import router as finance_router  # noqa: E402

app.include_router(mowing_router)
app.include_router(requests_router)
app.include_router(emails_router)
app.include_router(watering_router)
app.include_router(events_router)
app.include_router(recommendations_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(finance_router)

# Mount frontend static files (after API routes so /api/* takes priority)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
