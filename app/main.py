import logging
import logging.config
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.database import init_db
from app.routers import auth, clients, projects, design, email_quick, tasks, social, users, activity_log, quotes, yarn
from app.routers import files as files_router

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
})

logger = logging.getLogger(__name__)
logger.info("Starting Studio Manager (environment=%s)", settings.ENVIRONMENT)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kaayu Studio Manager",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Tighten allowed_origins in production via env var if needed.
# For now allows localhost dev origins; add your production domain here.
_cors_origins = ["http://localhost:8001", "http://127.0.0.1:8001"]
if settings.BASE_URL and settings.BASE_URL not in _cors_origins:
    _cors_origins.append(settings.BASE_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Auth guard ────────────────────────────────────────────────────────────────
# Pure ASGI middleware (avoids BaseHTTPMiddleware quirks in newer Starlette).
# Reads scope["session"] directly — guaranteed to run after SessionMiddleware
# has already populated it.
class RequireLoginMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Always allow: login/logout, static assets, health check
        if path in ("/login", "/logout", "/health") or path.startswith(("/static/", "/uploads/")):
            await self.app(scope, receive, send)
            return

        # SessionMiddleware (outer) already ran — scope["session"] is ready
        session = scope.get("session", {})
        user_id = session.get("user_id")

        if not user_id:
            response = RedirectResponse(url="/login", status_code=303)
            await response(scope, receive, send)
            return

        # Re-validate that the user is still active in the DB
        from app.database import SessionLocal
        from app.models.user import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
            if not user:
                scope["session"].clear()
                response = RedirectResponse(url="/login", status_code=303)
                await response(scope, receive, send)
                return
        except Exception:
            logger.exception("RequireLoginMiddleware: DB check failed for user_id=%s", user_id)
        finally:
            db.close()

        await self.app(scope, receive, send)


# Middleware order: SessionMiddleware added last → outermost → runs first.
# It populates scope["session"], then RequireLoginMiddleware reads it.
app.add_middleware(RequireLoginMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=settings.is_production,   # enforce Secure cookie flag in production
    max_age=7 * 24 * 60 * 60,           # 7 days
)

# ── Static files ──────────────────────────────────────────────────────────────
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# ── Templates ─────────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.globals["email_tool_url"] = settings.EMAIL_TOOL_URL



def _filesizeformat(value):
    if not value:
        return ""
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024:
            return f"{value:.0f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


templates.env.filters["filesizeformat"] = _filesizeformat

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(design.router)
app.include_router(email_quick.router)
app.include_router(tasks.router)
app.include_router(social.router)
app.include_router(files_router.router)
app.include_router(users.router)
app.include_router(quotes.router)
app.include_router(activity_log.router)
app.include_router(yarn.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
def health_check():
    """Used by load balancers and monitoring tools to verify the app is running."""
    from app.database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return JSONResponse({"status": status, "environment": settings.ENVIRONMENT}, status_code=200)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialised. App ready.")
