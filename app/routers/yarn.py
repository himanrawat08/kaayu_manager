import json
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.yarn import LOW_STOCK_THRESHOLD, YarnColor, YarnTransaction
from app.services.log_activity import log_activity
from app.utils.time import now_ist

router = APIRouter(prefix="/yarn")
templates = Jinja2Templates(directory="app/templates")


# ── Single aggregated query — replaces N+1 lazy loads ────────────────────────

def _color_stats(db: Session, color_code: str | None = None):
    """
    Return rows with (id, color_code, opening_stock, total_in, total_out).
    One SQL query regardless of how many colors exist.
    """
    q = (
        db.query(
            YarnColor.id,
            YarnColor.color_code,
            YarnColor.opening_stock,
            func.coalesce(
                func.sum(case(
                    (YarnTransaction.transaction_type == "in", YarnTransaction.quantity),
                    else_=0,
                )), 0
            ).label("total_in"),
            func.coalesce(
                func.sum(case(
                    (YarnTransaction.transaction_type == "out", YarnTransaction.quantity),
                    else_=0,
                )), 0
            ).label("total_out"),
        )
        .outerjoin(YarnTransaction, YarnColor.id == YarnTransaction.color_id)
        .group_by(YarnColor.id, YarnColor.color_code, YarnColor.opening_stock)
        .order_by(YarnColor.color_code)
    )
    if color_code:
        q = q.filter(YarnColor.color_code == color_code)
    return q.all()


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return now_ist().date()


# ── Inventory (main page) ─────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def yarn_inventory(request: Request, db: Session = Depends(get_db)):
    stats     = _color_stats(db)                         # 1 query
    projects  = db.query(Project).order_by(Project.name).all()

    low = out = 0
    balance_map: dict[str, int] = {}
    for r in stats:
        bal = int(r.opening_stock + r.total_in - r.total_out)
        balance_map[r.color_code] = bal
        if bal <= 0:
            out += 1
        elif bal < LOW_STOCK_THRESHOLD:
            low += 1

    # colors list is only needed for the datalist (id + code, no transactions)
    colors = db.query(YarnColor.id, YarnColor.color_code).order_by(YarnColor.color_code).all()

    return templates.TemplateResponse(request, "yarn/inventory.html", {
        "request": request,
        "colors": colors,
        "projects": projects,
        "total_colors": len(stats),
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
    stats = _color_stats(db)   # 1 query

    low = out = 0
    rows = []
    for r in stats:
        if search and search.lower() not in r.color_code.lower():
            continue
        bal = r.opening_stock + r.total_in - r.total_out
        rows.append({
            "id": r.id,
            "color_code": r.color_code,
            "opening_stock": r.opening_stock,
            "total_in": r.total_in,
            "total_out": r.total_out,
            "balance": bal,
        })
        if bal <= 0:
            out += 1
        elif bal < LOW_STOCK_THRESHOLD:
            low += 1

    return templates.TemplateResponse(request, "yarn/master.html", {
        "request": request,
        "rows": rows,
        "search": search,
        "total_colors": len(stats),
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
    return templates.TemplateResponse(request, "yarn/history.html", {
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

    # Pre-load all needed colors in one query
    needed = [cid for cid, qty in zip(color_id, quantity) if qty > 0]
    color_map = {c.id: c for c in db.query(YarnColor).filter(YarnColor.id.in_(needed)).all()}

    codes = []
    for cid, qty in zip(color_id, quantity):
        if qty <= 0 or cid not in color_map:
            continue
        db.add(YarnTransaction(
            color_id=cid, transaction_type="in", quantity=qty,
            date=parsed_date, project_id=None, notes=saved_notes,
        ))
        codes.append(f"{color_map[cid].color_code}+{int(qty)}")
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

    # Pre-load all needed colors in one query
    needed = [cid for cid, qty in zip(color_id, quantity) if qty > 0]
    color_map = {c.id: c for c in db.query(YarnColor).filter(YarnColor.id.in_(needed)).all()}

    codes = []
    for cid, qty in zip(color_id, quantity):
        if qty <= 0 or cid not in color_map:
            continue
        db.add(YarnTransaction(
            color_id=cid, transaction_type="out", quantity=qty,
            date=parsed_date, project_id=project_id, notes=saved_notes,
        ))
        codes.append(f"{color_map[cid].color_code}-{int(qty)}")
    db.commit()
    if codes:
        log_activity(db, request.session.get("user_name"), "Yarn bulk stock-out",
                     entity_type="yarn", detail=f"{', '.join(codes)} → {project.name}")
    return RedirectResponse(url="/yarn", status_code=303)


# ── Quick balance API ─────────────────────────────────────────────────────────

@router.get("/api/colors")
def yarn_colors_api(db: Session = Depends(get_db)):
    codes = [r[0] for r in db.query(YarnColor.color_code).order_by(YarnColor.color_code).all()]
    return JSONResponse(codes)


@router.get("/api/balance/{color_code}")
def yarn_balance_api(color_code: str, db: Session = Depends(get_db)):
    rows = _color_stats(db, color_code=color_code)
    if not rows:
        return JSONResponse({"found": False}, status_code=404)
    r = rows[0]
    bal = int(r.opening_stock + r.total_in - r.total_out)
    return JSONResponse({
        "found": True,
        "color_code": r.color_code,
        "balance": bal,
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
