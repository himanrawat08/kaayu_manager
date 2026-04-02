from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job_card import JobCard, JobCardItem
from app.models.project import Project
from app.models.vendor import Vendor
from app.services.log_activity import log_activity
from app.templates_config import templates

router = APIRouter(prefix="/job-cards")


def _next_job_card_number(db: Session) -> str:
    year = datetime.now().year
    existing = db.query(JobCard).filter(
        JobCard.job_card_number.like(f"JC-{year}-%")
    ).all()
    max_num = max(
        (int(c.job_card_number.rsplit("-", 1)[-1]) for c in existing),
        default=0,
    )
    return f"JC-{year}-{max_num + 1:03d}"


def _parse_float(s: str) -> float:
    try:
        return float(s.strip().replace(",", "") or 0)
    except ValueError:
        return 0.0


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s.strip()) if s.strip() else None
    except ValueError:
        return None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def job_card_list(request: Request, db: Session = Depends(get_db)):
    cards = db.query(JobCard).order_by(JobCard.id.desc()).all()
    return templates.TemplateResponse(request, "job_cards/list.html", {
        "request": request,
        "cards": cards,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
def job_card_new(request: Request, db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.name).all()
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse(request, "job_cards/form.html", {
        "request": request,
        "card": None,
        "vendors": vendors,
        "projects": projects,
    })


@router.post("/new")
def job_card_create(
    request: Request,
    vendor_id: int = Form(...),
    project_id: str = Form(""),
    receive_by_date: str = Form(""),
    notes: str = Form(""),
    particular_name: List[str] = Form(default=[]),
    size: List[str] = Form(default=[]),
    quantity: List[str] = Form(default=[]),
    rate: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        return RedirectResponse(url="/job-cards/new", status_code=303)

    pid = int(project_id) if project_id.strip().isdigit() else None

    card = JobCard(
        job_card_number=_next_job_card_number(db),
        vendor_id=vendor_id,
        project_id=pid,
        receive_by_date=_parse_date(receive_by_date),
        notes=notes.strip() or None,
    )
    db.add(card)
    db.flush()

    for i, name in enumerate(particular_name):
        name = name.strip()
        if not name:
            continue
        qty = _parse_float(quantity[i] if i < len(quantity) else "1") or 1
        rt = _parse_float(rate[i] if i < len(rate) else "0")
        db.add(JobCardItem(
            job_card_id=card.id,
            sr_no=i + 1,
            particular_name=name,
            size=(size[i].strip() if i < len(size) else "") or None,
            quantity=qty,
            rate=rt,
            amount=round(qty * rt, 2),
        ))

    db.commit()
    log_activity(db, request.session.get("user_name"), "Created job card",
                 entity_type="job_card", entity_id=card.id, detail=card.job_card_number)
    return RedirectResponse(url=f"/job-cards/{card.id}", status_code=303)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{card_id}", response_class=HTMLResponse)
def job_card_detail(request: Request, card_id: int, db: Session = Depends(get_db)):
    card = db.query(JobCard).filter(JobCard.id == card_id).first()
    if not card:
        return RedirectResponse(url="/job-cards", status_code=303)
    return templates.TemplateResponse(request, "job_cards/detail.html", {
        "request": request,
        "card": card,
    })


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.get("/{card_id}/edit", response_class=HTMLResponse)
def job_card_edit_form(request: Request, card_id: int, db: Session = Depends(get_db)):
    card = db.query(JobCard).filter(JobCard.id == card_id).first()
    if not card:
        return RedirectResponse(url="/job-cards", status_code=303)
    vendors = db.query(Vendor).order_by(Vendor.name).all()
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse(request, "job_cards/form.html", {
        "request": request,
        "card": card,
        "vendors": vendors,
        "projects": projects,
    })


@router.post("/{card_id}/edit")
def job_card_update(
    request: Request,
    card_id: int,
    vendor_id: int = Form(...),
    project_id: str = Form(""),
    receive_by_date: str = Form(""),
    notes: str = Form(""),
    particular_name: List[str] = Form(default=[]),
    size: List[str] = Form(default=[]),
    quantity: List[str] = Form(default=[]),
    rate: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    card = db.query(JobCard).filter(JobCard.id == card_id).first()
    if not card:
        return RedirectResponse(url="/job-cards", status_code=303)

    pid = int(project_id) if project_id.strip().isdigit() else None
    card.vendor_id = vendor_id
    card.project_id = pid
    card.receive_by_date = _parse_date(receive_by_date)
    card.notes = notes.strip() or None

    for existing in list(card.items):
        db.delete(existing)
    db.flush()

    for i, name in enumerate(particular_name):
        name = name.strip()
        if not name:
            continue
        qty = _parse_float(quantity[i] if i < len(quantity) else "1") or 1
        rt = _parse_float(rate[i] if i < len(rate) else "0")
        db.add(JobCardItem(
            job_card_id=card.id,
            sr_no=i + 1,
            particular_name=name,
            size=(size[i].strip() if i < len(size) else "") or None,
            quantity=qty,
            rate=rt,
            amount=round(qty * rt, 2),
        ))

    db.commit()
    log_activity(db, request.session.get("user_name"), "Updated job card",
                 entity_type="job_card", entity_id=card.id, detail=card.job_card_number)
    return RedirectResponse(url=f"/job-cards/{card_id}", status_code=303)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.post("/{card_id}/delete")
def job_card_delete(request: Request, card_id: int, db: Session = Depends(get_db)):
    card = db.query(JobCard).filter(JobCard.id == card_id).first()
    if card:
        number = card.job_card_number
        db.delete(card)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted job card",
                     entity_type="job_card", detail=number)
    return RedirectResponse(url="/job-cards", status_code=303)
