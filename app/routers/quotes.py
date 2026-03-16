from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.quotation import (
    Quotation, QuoteItem, QuoteSundry,
    QUOTE_STATUSES, QUOTE_STATUS_LABELS, QUOTE_STATUS_CLS,
)
from app.services.log_activity import log_activity
from app.utils.time import now_ist

router = APIRouter(prefix="/quotes")
templates = Jinja2Templates(directory="app/templates")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_quote_number(db: Session) -> str:
    year = str(now_ist().year)[2:]
    count = db.query(func.count(Quotation.id)).scalar() + 1
    return f"QT{year}{count:03d}"


def _recalculate(q: Quotation) -> None:
    """Recalculate all totals using Decimal arithmetic to avoid float rounding errors."""
    D = Decimal
    items_sub    = sum(D(str(item.amount)) for item in q.items)
    sundries_sub = sum(D(str(s.amount))    for s in q.sundries)
    subtotal     = (items_sub + sundries_sub).quantize(D("1"), rounding=ROUND_HALF_UP)
    taxable      = subtotal
    cgst  = (taxable * D(str(q.cgst_percent or 0)) / 100).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    sgst  = (taxable * D(str(q.sgst_percent or 0)) / 100).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    igst  = (taxable * D(str(q.igst_percent or 0)) / 100).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    total = (taxable + cgst + sgst + igst).quantize(D("1"), rounding=ROUND_HALF_UP)

    q.subtotal        = float(subtotal)
    q.discount_type   = None
    q.discount_value  = 0.0
    q.discount_amount = 0.0
    q.taxable_amount  = float(subtotal)
    q.cgst_amount     = float(cgst)
    q.sgst_amount     = float(sgst)
    q.igst_amount     = float(igst)
    q.total_amount    = float(total)


def _parse_float(s: str) -> float:
    try:
        return float(s.strip().replace(",", "") or 0)
    except ValueError:
        return 0.0


def _clamp_percent(s: str) -> float:
    """Parse a tax percentage and clamp to [0, 100]."""
    v = _parse_float(s)
    return max(0.0, min(100.0, v))


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s.strip()) if s.strip() else None
    except ValueError:
        return None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def quotes_list(
    request: Request,
    status: str = "",
    project_id: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Quotation)
    if status and status in QUOTE_STATUSES:
        query = query.filter(Quotation.status == status)
    if project_id.strip().isdigit():
        query = query.filter(Quotation.project_id == int(project_id))
    quotes = query.order_by(Quotation.created_at.desc()).all()
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse("quotes/list.html", {
        "request": request,
        "quotes": quotes,
        "projects": projects,
        "status_filter": status,
        "project_filter": project_id,
        "status_labels": QUOTE_STATUS_LABELS,
        "status_cls": QUOTE_STATUS_CLS,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
def quotes_new_form(request: Request, project_id: str = "", db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse("quotes/form.html", {
        "request": request,
        "quote": None,
        "projects": projects,
        "prefill_project_id": project_id,
        "status_labels": QUOTE_STATUS_LABELS,
    })


@router.post("/new")
def quotes_create(
    request: Request,
    project_id: int = Form(...),
    valid_until: str = Form(""),
    notes: str = Form(""),
    terms_conditions: str = Form(""),
    cgst_percent: str = Form("9"),
    sgst_percent: str = Form("9"),
    igst_percent: str = Form("0"),
    item_name: List[str] = Form(default=[]),
    size: List[str] = Form(default=[]),
    description: List[str] = Form(default=[]),
    qty: List[str] = Form(default=[]),
    unit: List[str] = Form(default=[]),
    unit_price: List[str] = Form(default=[]),
    sundry_particular: List[str] = Form(default=[]),
    sundry_amount: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/quotes/new", status_code=303)

    max_ver = db.query(func.max(Quotation.version)).filter(
        Quotation.project_id == project_id
    ).scalar() or 0

    q = Quotation(
        quote_number=_generate_quote_number(db),
        project_id=project_id,
        version=max_ver + 1,
        status="draft",
        valid_until=_parse_date(valid_until),
        notes=notes.strip() or None,
        terms_conditions=terms_conditions.strip() or None,
        cgst_percent=_clamp_percent(cgst_percent),
        sgst_percent=_clamp_percent(sgst_percent),
        igst_percent=_clamp_percent(igst_percent),
    )
    db.add(q)
    db.flush()

    for i, name in enumerate(item_name):
        name = name.strip()
        if not name:
            continue
        q_qty   = _parse_float(qty[i] if i < len(qty) else "1") or 1
        q_price = _parse_float(unit_price[i] if i < len(unit_price) else "0")
        db.add(QuoteItem(
            quote_id=q.id,
            sort_order=i,
            size=(size[i].strip() if i < len(size) else "") or None,
            item_name=name,
            description=(description[i].strip() if i < len(description) else "") or None,
            qty=q_qty,
            unit=(unit[i].strip() if i < len(unit) else "") or "pcs",
            unit_price=q_price,
            amount=round(q_qty * q_price, 2),
        ))

    for i, particular in enumerate(sundry_particular):
        particular = particular.strip()
        if not particular:
            continue
        s_amount = _parse_float(sundry_amount[i] if i < len(sundry_amount) else "0")
        db.add(QuoteSundry(
            quote_id=q.id,
            sort_order=i,
            particular=particular,
            amount=s_amount,
        ))

    db.flush()
    db.refresh(q)
    _recalculate(q)
    db.commit()

    log_activity(db, request.session.get("user_name"), "Created quote",
                 entity_type="quote", entity_id=q.id, detail=q.quote_number)
    return RedirectResponse(url=f"/quotes/{q.id}", status_code=303)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{quote_id}", response_class=HTMLResponse)
def quotes_detail(
    request: Request,
    quote_id: int,
    success: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        return RedirectResponse(url="/quotes", status_code=303)

    return templates.TemplateResponse("quotes/detail.html", {
        "request": request,
        "q": q,
        "status_labels": QUOTE_STATUS_LABELS,
        "status_cls": QUOTE_STATUS_CLS,
        "success": success or None,
        "error": error or None,
    })


# ── Print / PDF ────────────────────────────────────────────────────────────────

@router.get("/{quote_id}/print", response_class=HTMLResponse)
def quotes_print(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        return RedirectResponse(url="/quotes", status_code=303)
    return templates.TemplateResponse("quotes/print.html", {
        "request": request,
        "q": q,
        "status_labels": QUOTE_STATUS_LABELS,
    })


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.get("/{quote_id}/edit", response_class=HTMLResponse)
def quotes_edit_form(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        return RedirectResponse(url="/quotes", status_code=303)
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse("quotes/form.html", {
        "request": request,
        "quote": q,
        "projects": projects,
        "prefill_project_id": str(q.project_id),
        "status_labels": QUOTE_STATUS_LABELS,
    })


@router.post("/{quote_id}/edit")
def quotes_update(
    request: Request,
    quote_id: int,
    valid_until: str = Form(""),
    notes: str = Form(""),
    terms_conditions: str = Form(""),
    cgst_percent: str = Form("9"),
    sgst_percent: str = Form("9"),
    igst_percent: str = Form("0"),
    item_name: List[str] = Form(default=[]),
    size: List[str] = Form(default=[]),
    description: List[str] = Form(default=[]),
    qty: List[str] = Form(default=[]),
    unit: List[str] = Form(default=[]),
    unit_price: List[str] = Form(default=[]),
    sundry_particular: List[str] = Form(default=[]),
    sundry_amount: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        return RedirectResponse(url="/quotes", status_code=303)

    q.valid_until      = _parse_date(valid_until)
    q.notes            = notes.strip() or None
    q.terms_conditions = terms_conditions.strip() or None
    q.cgst_percent     = _clamp_percent(cgst_percent)
    q.sgst_percent     = _clamp_percent(sgst_percent)
    q.igst_percent     = _clamp_percent(igst_percent)

    # Replace all items
    for existing in list(q.items):
        db.delete(existing)
    for existing in list(q.sundries):
        db.delete(existing)
    db.flush()

    for i, name in enumerate(item_name):
        name = name.strip()
        if not name:
            continue
        q_qty   = _parse_float(qty[i] if i < len(qty) else "1") or 1
        q_price = _parse_float(unit_price[i] if i < len(unit_price) else "0")
        db.add(QuoteItem(
            quote_id=q.id,
            sort_order=i,
            size=(size[i].strip() if i < len(size) else "") or None,
            item_name=name,
            description=(description[i].strip() if i < len(description) else "") or None,
            qty=q_qty,
            unit=(unit[i].strip() if i < len(unit) else "") or "pcs",
            unit_price=q_price,
            amount=round(q_qty * q_price, 2),
        ))

    for i, particular in enumerate(sundry_particular):
        particular = particular.strip()
        if not particular:
            continue
        s_amount = _parse_float(sundry_amount[i] if i < len(sundry_amount) else "0")
        db.add(QuoteSundry(
            quote_id=q.id,
            sort_order=i,
            particular=particular,
            amount=s_amount,
        ))

    db.flush()
    db.refresh(q)
    _recalculate(q)
    db.commit()

    log_activity(db, request.session.get("user_name"), "Updated quote",
                 entity_type="quote", entity_id=q.id, detail=q.quote_number)
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


# ── Status changes ────────────────────────────────────────────────────────────

@router.post("/{quote_id}/send")
def quotes_send(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if q and q.status == "draft":
        q.status = "sent"
        q.sent_at = now_ist()
        db.commit()
        log_activity(db, request.session.get("user_name"), "Marked quote as sent",
                     entity_type="quote", entity_id=q.id, detail=q.quote_number)
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.post("/{quote_id}/accept")
def quotes_accept(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if q and q.status == "sent":
        db.query(Quotation).filter(
            Quotation.project_id == q.project_id,
            Quotation.id != quote_id,
        ).update({"is_final": False})
        q.status = "accepted"
        q.is_final = True
        q.accepted_at = now_ist()
        db.commit()
        log_activity(db, request.session.get("user_name"), "Accepted quote",
                     entity_type="quote", entity_id=q.id, detail=q.quote_number)
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.post("/{quote_id}/reject")
def quotes_reject(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if q and q.status == "sent":
        q.status = "rejected"
        db.commit()
        log_activity(db, request.session.get("user_name"), "Rejected quote",
                     entity_type="quote", entity_id=q.id, detail=q.quote_number)
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.post("/{quote_id}/revert")
def quotes_revert(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if q and q.status in ("sent", "rejected"):
        q.status = "draft"
        q.sent_at = None
        db.commit()
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


# ── New version ───────────────────────────────────────────────────────────────

@router.post("/{quote_id}/new-version")
def quotes_new_version(request: Request, quote_id: int, db: Session = Depends(get_db)):
    original = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not original:
        return RedirectResponse(url="/quotes", status_code=303)

    max_ver = db.query(func.max(Quotation.version)).filter(
        Quotation.project_id == original.project_id
    ).scalar() or 0

    new_q = Quotation(
        quote_number=_generate_quote_number(db),
        project_id=original.project_id,
        version=max_ver + 1,
        status="draft",
        valid_until=original.valid_until,
        notes=original.notes,
        terms_conditions=original.terms_conditions,
        cgst_percent=original.cgst_percent,
        sgst_percent=original.sgst_percent,
        igst_percent=original.igst_percent,
    )
    db.add(new_q)
    db.flush()

    for item in original.items:
        db.add(QuoteItem(
            quote_id=new_q.id,
            sort_order=item.sort_order,
            size=item.size,
            item_name=item.item_name,
            description=item.description,
            qty=item.qty,
            unit=item.unit,
            unit_price=item.unit_price,
            amount=item.amount,
        ))

    for s in original.sundries:
        db.add(QuoteSundry(
            quote_id=new_q.id,
            sort_order=s.sort_order,
            particular=s.particular,
            amount=s.amount,
        ))

    db.flush()
    db.refresh(new_q)
    _recalculate(new_q)
    db.commit()

    log_activity(db, request.session.get("user_name"), "Created new quote version",
                 entity_type="quote", entity_id=new_q.id, detail=new_q.quote_number)
    return RedirectResponse(url=f"/quotes/{new_q.id}", status_code=303)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.post("/{quote_id}/delete")
def quotes_delete(request: Request, quote_id: int, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if q:
        number = q.quote_number or str(q.id)
        db.delete(q)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted quote",
                     entity_type="quote", detail=number)
    return RedirectResponse(url="/quotes", status_code=303)
