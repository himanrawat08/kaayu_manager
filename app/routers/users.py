from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, USER_ROLES, USER_ROLE_LABELS, USER_ROLE_CLS, hash_password
from app.services.log_activity import log_activity

router = APIRouter(prefix="/users")
templates = Jinja2Templates(directory="app/templates")


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(request, "users/list.html", {
        "request": request,
        "users": users,
        "role_labels": USER_ROLE_LABELS,
        "role_cls": USER_ROLE_CLS,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
def users_new_form(request: Request):
    return templates.TemplateResponse(request, "users/form.html", {
        "request": request,
        "user": None,
        "roles": USER_ROLES,
        "role_labels": USER_ROLE_LABELS,
        "error": None,
    })


@router.post("/new")
def users_create(
    request:   Request,
    username:  str = Form(...),
    full_name: str = Form(...),
    password:  str = Form(...),
    password2: str = Form(...),
    email:     str = Form(""),
    phone:     str = Form(""),
    role:      str = Form("sales"),
    db: Session = Depends(get_db),
):
    # Validate
    if password != password2:
        from fastapi import Request as Req
        # Re-render with error via redirect (no request obj here — use query param)
        return RedirectResponse(url="/users/new?error=Passwords+do+not+match", status_code=303)

    existing = db.query(User).filter(User.username == username.strip().lower()).first()
    if existing:
        return RedirectResponse(url="/users/new?error=Username+already+taken", status_code=303)

    if role not in USER_ROLES:
        role = "sales"

    user = User(
        username=username.strip().lower(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        email=email.strip() or None,
        phone=phone.strip() or None,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    log_activity(db, request.session.get("user_name"), "Created user",
                 entity_type="user", detail=f"{full_name.strip()} ({role})")
    return RedirectResponse(url="/users?success=User+created", status_code=303)


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.get("/{user_id}/edit", response_class=HTMLResponse)
def users_edit_form(
    request: Request,
    user_id: int,
    error: str = "",
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    return templates.TemplateResponse(request, "users/form.html", {
        "request": request,
        "user": user,
        "roles": USER_ROLES,
        "role_labels": USER_ROLE_LABELS,
        "error": error or None,
    })


@router.post("/{user_id}/edit")
def users_update(
    request:   Request,
    user_id:   int,
    full_name: str = Form(...),
    password:  str = Form(""),
    password2: str = Form(""),
    email:     str = Form(""),
    phone:     str = Form(""),
    role:      str = Form("sales"),
    is_active: str = Form("on"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)

    if password:
        if password != password2:
            return RedirectResponse(
                url=f"/users/{user_id}/edit?error=Passwords+do+not+match", status_code=303
            )
        user.password_hash = hash_password(password)

    user.full_name = full_name.strip()
    user.email = email.strip() or None
    user.phone = phone.strip() or None
    user.role = role if role in USER_ROLES else user.role
    user.is_active = (is_active == "on")
    db.commit()
    log_activity(db, request.session.get("user_name"), "Updated user",
                 entity_type="user", entity_id=user_id, detail=user.full_name)
    return RedirectResponse(url="/users?success=User+updated", status_code=303)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/delete")
def users_delete(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        name = user.full_name
        db.delete(user)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted user",
                     entity_type="user", detail=name)
    return RedirectResponse(url="/users?success=User+deleted", status_code=303)
