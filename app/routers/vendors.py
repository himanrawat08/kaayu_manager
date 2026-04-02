from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import Vendor
from app.templates_config import templates

router = APIRouter(prefix="/vendors")


@router.get("", response_class=HTMLResponse)
def vendor_list(request: Request, db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.name).all()
    return templates.TemplateResponse(request, "vendors/list.html", {
        "request": request,
        "vendors": vendors,
    })


@router.get("/new", response_class=HTMLResponse)
def vendor_new(request: Request):
    return templates.TemplateResponse(request, "vendors/form.html", {
        "request": request,
        "vendor": None,
    })


@router.post("/new")
def vendor_create(
    request: Request,
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    db: Session = Depends(get_db),
):
    v = Vendor(
        name=name.strip(),
        contact_name=contact_name.strip() or None,
        phone=phone.strip() or None,
        email=email.strip() or None,
        address=address.strip() or None,
    )
    db.add(v)
    db.commit()
    return RedirectResponse(url="/vendors", status_code=303)


@router.get("/{vendor_id}/edit", response_class=HTMLResponse)
def vendor_edit_form(request: Request, vendor_id: int, db: Session = Depends(get_db)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        return RedirectResponse(url="/vendors", status_code=303)
    return templates.TemplateResponse(request, "vendors/form.html", {
        "request": request,
        "vendor": v,
    })


@router.post("/{vendor_id}/edit")
def vendor_update(
    request: Request,
    vendor_id: int,
    name: str = Form(...),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    db: Session = Depends(get_db),
):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        return RedirectResponse(url="/vendors", status_code=303)
    v.name = name.strip()
    v.contact_name = contact_name.strip() or None
    v.phone = phone.strip() or None
    v.email = email.strip() or None
    v.address = address.strip() or None
    db.commit()
    return RedirectResponse(url="/vendors", status_code=303)


@router.post("/{vendor_id}/delete")
def vendor_delete(request: Request, vendor_id: int, db: Session = Depends(get_db)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if v:
        db.delete(v)
        db.commit()
    return RedirectResponse(url="/vendors", status_code=303)
