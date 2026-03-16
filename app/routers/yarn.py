import json
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.yarn import LOW_STOCK_THRESHOLD, YarnColor, YarnTransaction
from app.services.log_activity import log_activity
from app.utils.time import now_ist

router = APIRouter(prefix="/yarn")
templates = Jinja2Templates(directory="app/templates")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_totals(color: YarnColor) -> tuple[float, float, float]:
    """Return (total_in, total_out, balance)."""
    total_in  = sum(t.quantity for t in color.transactions if t.transaction_type == "in")
    total_out = sum(t.quantity for t in color.transactions if t.transaction_type == "out")
    return total_in, total_out, color.opening_stock + total_in - total_out


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return now_ist().date()


def _stats(colors: list[YarnColor]) -> tuple[int, int, int]:
    """Return (total, low_stock_count, out_of_stock_count)."""
    low = out = 0
    for c in colors:
        _, _, bal = _compute_totals(c)
        if bal <= 0:
            out += 1
        elif bal < LOW_STOCK_THRESHOLD:
            low += 1
    return len(colors), low, out


# ── Inventory (main page) ─────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def yarn_inventory(request: Request, db: Session = Depends(get_db)):
    colors   = db.query(YarnColor).order_by(YarnColor.color_code).all()
    projects = db.query(Project).order_by(Project.name).all()
    total, low, out = _stats(colors)

    # Build balance map for client-side Check Stock and chip modals
    balance_map: dict[str, int] = {}
    for c in colors:
        _, _, bal = _compute_totals(c)
        balance_map[c.color_code] = int(bal)

    return templates.TemplateResponse("yarn/inventory.html", {
        "request": request,
        "colors": colors,
        "projects": projects,
        "total_colors": total,
        "low_stock_count": low,
        "out_of_stock_count": out,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
        "today": now_ist().date().isoformat(),
        "balance_map_json": json.dumps(balance_map),
    })


# ── Master table ──────────────────────────────────────────────────────────────

@router.get("/master", response_class=HTMLResponse)
def yarn_master(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
):
    colors = db.query(YarnColor).order_by(YarnColor.color_code).all()
    rows = []
    for c in colors:
        if search and search.lower() not in c.color_code.lower():
            continue
        total_in, total_out, balance = _compute_totals(c)
        rows.append({
            "id": c.id,
            "color_code": c.color_code,
            "opening_stock": c.opening_stock,
            "total_in": total_in,
            "total_out": total_out,
            "balance": balance,
        })
    total, low, out = _stats(colors)
    return templates.TemplateResponse("yarn/master.html", {
        "request": request,
        "rows": rows,
        "search": search,
        "total_colors": total,
        "low_stock_count": low,
        "out_of_stock_count": out,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
    })


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history", response_class=HTMLResponse)
def yarn_history(
    request: Request,
    color: str = "",
    tx_type: str = "",
    project_id: str = "",
    date_from: str = "",
    date_to: str = "",
    db: Session = Depends(get_db),
):
    query = (
        db.query(YarnTransaction)
        .join(YarnColor)
        .order_by(YarnTransaction.date.desc(), YarnTransaction.id.desc())
    )
    if color.strip():
        query = query.filter(YarnColor.color_code.ilike(f"%{color.strip()}%"))
    if tx_type in ("in", "out"):
        query = query.filter(YarnTransaction.transaction_type == tx_type)
    if project_id.strip().isdigit():
        query = query.filter(YarnTransaction.project_id == int(project_id))
    if date_from.strip():
        try:
            query = query.filter(YarnTransaction.date >= date.fromisoformat(date_from.strip()))
        except ValueError:
            pass
    if date_to.strip():
        try:
            query = query.filter(YarnTransaction.date <= date.fromisoformat(date_to.strip()))
        except ValueError:
            pass

    transactions = query.all()
    projects = db.query(Project).order_by(Project.name).all()
    return templates.TemplateResponse("yarn/history.html", {
        "request": request,
        "transactions": transactions,
        "projects": projects,
        "filter_color": color,
        "filter_type": tx_type,
        "filter_project_id": project_id,
        "filter_date_from": date_from,
        "filter_date_to": date_to,
    })


# ── Bulk Stock In ─────────────────────────────────────────────────────────────

@router.post("/stock-in")
def yarn_stock_in(
    request: Request,
    color_id: List[int] = Form(...),
    quantity: List[float] = Form(...),
    tx_date: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    parsed_date = _parse_date(tx_date)
    saved_notes = notes.strip() or None
    codes = []
    for cid, qty in zip(color_id, quantity):
        if qty <= 0:
            continue
        color = db.query(YarnColor).filter(YarnColor.id == cid).first()
        if not color:
            continue
        db.add(YarnTransaction(
            color_id=cid,
            transaction_type="in",
            quantity=qty,
            date=parsed_date,
            project_id=None,
            notes=saved_notes,
        ))
        codes.append(f"{color.color_code}+{int(qty)}")
    db.commit()
    if codes:
        log_activity(db, request.session.get("user_name"), "Yarn bulk stock-in",
                     entity_type="yarn", detail=", ".join(codes))
    return RedirectResponse(url="/yarn", status_code=303)


# ── Bulk Stock Out ────────────────────────────────────────────────────────────

@router.post("/stock-out")
def yarn_stock_out(
    request: Request,
    color_id: List[int] = Form(...),
    quantity: List[float] = Form(...),
    tx_date: str = Form(...),
    project_id: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/yarn", status_code=303)

    parsed_date = _parse_date(tx_date)
    saved_notes = notes.strip() or None
    codes = []
    for cid, qty in zip(color_id, quantity):
        if qty <= 0:
            continue
        color = db.query(YarnColor).filter(YarnColor.id == cid).first()
        if not color:
            continue
        db.add(YarnTransaction(
            color_id=cid,
            transaction_type="out",
            quantity=qty,
            date=parsed_date,
            project_id=project_id,
            notes=saved_notes,
        ))
        codes.append(f"{color.color_code}-{int(qty)}")
    db.commit()
    if codes:
        log_activity(db, request.session.get("user_name"), "Yarn bulk stock-out",
                     entity_type="yarn",
                     detail=f"{', '.join(codes)} → {project.name}")
    return RedirectResponse(url="/yarn", status_code=303)


# ── Quick balance API (used by dashboard lookup) ─────────────────────────────

@router.get("/api/colors")
def yarn_colors_api(db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    codes = [c.color_code for c in db.query(YarnColor.color_code).order_by(YarnColor.color_code).all()]
    return JSONResponse(codes)


@router.get("/api/balance/{color_code}")
def yarn_balance_api(color_code: str, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    color = db.query(YarnColor).filter(YarnColor.color_code == color_code).first()
    if not color:
        return JSONResponse({"found": False}, status_code=404)
    _, _, bal = _compute_totals(color)
    return JSONResponse({
        "found": True,
        "color_code": color.color_code,
        "balance": int(bal),
        "low": 0 < bal < LOW_STOCK_THRESHOLD,
        "out": bal <= 0,
    })


# ── Delete Transaction ────────────────────────────────────────────────────────

@router.post("/transactions/{tx_id}/delete")
def yarn_delete_transaction(
    request: Request,
    tx_id: int,
    db: Session = Depends(get_db),
):
    tx = db.query(YarnTransaction).filter(YarnTransaction.id == tx_id).first()
    if tx:
        detail = f"{tx.color.color_code} {tx.transaction_type} {tx.quantity}"
        db.delete(tx)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted yarn transaction",
                     entity_type="yarn", detail=detail)
    return RedirectResponse(url="/yarn/history", status_code=303)
