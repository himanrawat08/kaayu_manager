import logging
import logging.config
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.database import init_db
from app.templates_config import templates
from app.routers import auth, clients, projects, design, email_quick, tasks, social, users, activity_log, quotes, yarn, leads
from app.routers import files as files_router
from app.permissions import require_permission

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

        # Idle timeout — log out after 8 hours of inactivity
        IDLE_TIMEOUT = 8 * 3600
        last_active = session.get("last_active", 0)
        if last_active and time.time() - last_active > IDLE_TIMEOUT:
            session.clear()
            response = RedirectResponse(url="/login", status_code=303)
            await response(scope, receive, send)
            return
        session["last_active"] = time.time()

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

        # Viewer / Supervisor roles: read-only — block all mutating methods
        if session.get("user_role") in ("viewer", "supervisor") and scope["method"] in ("POST", "PUT", "DELETE", "PATCH"):
            from starlette.responses import Response
            response = Response("Forbidden", status_code=403)
            await response(scope, receive, send)
            return

        # Supervisor role: block contacts and phonebook paths
        if session.get("user_role") == "supervisor" and (
            path.startswith("/contacts") or path.startswith("/phonebook")
        ):
            from starlette.responses import Response
            response = Response("Forbidden", status_code=403)
            await response(scope, receive, send)
            return

        # Supervisor role: block project create/edit pages
        import re as _re
        if session.get("user_role") == "supervisor" and (
            path == "/projects/new"
            or _re.match(r"^/projects/\d+/edit$", path)
        ):
            from starlette.responses import Response
            response = Response("Forbidden", status_code=403)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# Middleware order: SessionMiddleware added last → outermost → runs first.
# It populates scope["session"], then RequireLoginMiddleware reads it.
app.add_middleware(RequireLoginMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=settings.is_production,   # enforce Secure cookie flag in production
    max_age=None,                        # session cookie — expires when browser closes
)

# ── Static files ──────────────────────────────────────────────────────────────
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# ── Templates ─────────────────────────────────────────────────────────────────

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
app.include_router(email_quick.router)
app.include_router(yarn.router)
app.include_router(leads.router,          dependencies=[require_permission("leads")])
app.include_router(quotes.router,         dependencies=[require_permission("quotations")])
app.include_router(design.router,         dependencies=[require_permission("design_files")])
app.include_router(files_router.router,   dependencies=[require_permission("production_files")])
app.include_router(tasks.router,          dependencies=[require_permission("tasks")])
app.include_router(social.router,         dependencies=[require_permission("social")])
app.include_router(activity_log.router,   dependencies=[require_permission("activity_log")])
app.include_router(users.router,          dependencies=[require_permission("user_management")])


# ── Exception handlers ────────────────────────────────────────────────────────
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exception_handlers import http_exception_handler as _default_http_exc_handler


@app.exception_handler(FastAPIHTTPException)
async def custom_http_exc_handler(request, exc):
    if exc.status_code == 403:
        return templates.TemplateResponse("403.html", {"request": request}, status_code=403)
    return await _default_http_exc_handler(request, exc)


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
