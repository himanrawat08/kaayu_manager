import threading
import time
from collections import defaultdict
from datetime import datetime

from app.utils.time import now_ist

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, verify_password, hash_password
from app.services.log_activity import log_activity

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ── Image cycling ─────────────────────────────────────────────────────────────

LOGIN_IMAGES = [
    "DSC04375.jpg",
    "DSC05805-3.jpg",
    "DSC06380-Edit.jpg",
    "IMG_5179.jpg",
    "Rhythms of Nature.jpg",
    "c26627f1-88b7-4c57-8685-7f5298f50da2.jpg",
]

_counter = 0
_lock = threading.Lock()


def _next_image() -> str:
    global _counter
    with _lock:
        img = LOGIN_IMAGES[_counter % len(LOGIN_IMAGES)]
        _counter += 1
    return img


# ── Rate limiter (20 attempts per 15 minutes per IP) ─────────────────────────

_login_attempts: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()
_RATE_WINDOW = 15 * 60   # 15 minutes in seconds
_RATE_MAX    = 20        # max attempts per window


def _is_rate_limited(ip: str) -> bool:
    """Returns True if this IP has exceeded the login attempt limit."""
    now = time.time()
    with _rate_lock:
        valid = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
        _login_attempts[ip] = valid
        if len(valid) >= _RATE_MAX:
            return True
        _login_attempts[ip].append(now)
        return False


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {
        "request": request,
        "image": _next_image(),
        "error": error,
    })


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        return RedirectResponse(
            url="/login?error=Too+many+login+attempts.+Please+wait+15+minutes.", status_code=303
        )

    user = db.query(User).filter(
        User.username == username.strip().lower(),
    ).first()

    # Generic error — same message whether user missing or password wrong
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return RedirectResponse(
            url="/login?error=Invalid+username+or+password", status_code=303
        )

    # Update last login timestamp
    user.last_login = now_ist()
    db.commit()

    request.session["user_id"]   = user.id
    request.session["user_name"] = user.full_name
    request.session["user_role"] = user.role

    # Log the login event
    log_activity(db, user.full_name, "Logged in", entity_type="user", entity_id=user.id)

    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ── Change Password ───────────────────────────────────────────────────────────

@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request, error: str = "", success: str = ""):
    return templates.TemplateResponse(request, "change_password.html", {
        "request": request,
        "error": error or None,
        "success": success or None,
    })


@router.post("/change-password")
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not verify_password(current_password, user.password_hash):
        return RedirectResponse(url="/change-password?error=Current+password+is+incorrect", status_code=303)

    if new_password != new_password2:
        return RedirectResponse(url="/change-password?error=New+passwords+do+not+match", status_code=303)

    if len(new_password) < 6:
        return RedirectResponse(url="/change-password?error=Password+must+be+at+least+6+characters", status_code=303)

    user.password_hash = hash_password(new_password)
    db.commit()

    log_activity(db, user.full_name, "Changed password", entity_type="user", entity_id=user.id)

    return RedirectResponse(url="/change-password?success=Password+changed+successfully", status_code=303)
