import csv
import io
import json
from datetime import date as date_type, datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.activity import ClientActivity, ACTIVITY_TYPES
from app.models.project import Project, STAGES, STAGE_LABELS
from app.models.project_files import DesignFile
from app.models.social_post import SocialPost
from app.models.task import Task, TASK_PRIORITIES, TASK_PRIORITY_LABELS
from app.models.yarn import LOW_STOCK_THRESHOLD
from app.routers.yarn import _color_stats
from app.services.contact_sync import sync_contact
from app.services.log_activity import log_activity
from app.constants import INDIAN_CITIES
from app.templates_config import templates

router = APIRouter()


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, view: str = "overview", db: Session = Depends(get_db)):
    total_clients = db.query(func.count(Client.id)).scalar()
    active_projects = db.query(func.count(Project.id)).filter(Project.status == "active").scalar()
    on_hold = db.query(func.count(Project.id)).filter(Project.status == "on_hold").scalar()
    completed = db.query(func.count(Project.id)).filter(Project.status == "completed").scalar()

    stage_counts = []
    for stage in STAGES:
        count = (
            db.query(func.count(Project.id))
            .filter(Project.current_stage == stage, Project.status == "active")
            .scalar()
        )
        stage_counts.append((stage, STAGE_LABELS[stage], count))

    recent_projects = (
        db.query(Project)
        .order_by(Project.updated_at.desc())
        .limit(8)
        .all()
    )

    # Tasks — all, pending first sorted by due date
    all_tasks = (
        db.query(Task)
        .order_by(Task.is_completed, Task.due_date.asc().nullslast(), Task.created_at.asc())
        .all()
    )
    today = date_type.today()
    overdue_tasks  = [t for t in all_tasks if not t.is_completed and t.due_date and t.due_date < today]
    today_tasks    = [t for t in all_tasks if not t.is_completed and t.due_date and t.due_date == today]
    upcoming_tasks = [t for t in all_tasks if not t.is_completed and t.due_date and t.due_date > today]
    no_due_tasks   = [t for t in all_tasks if not t.is_completed and not t.due_date]
    done_tasks     = [t for t in all_tasks if t.is_completed]

    # Active projects for task creation dropdown
    active_projects_list = (
        db.query(Project)
        .filter(Project.status == "active")
        .order_by(Project.name)
        .all()
    )

    # Calendar events (all dated items)
    cal_events = []
    for t in all_tasks:
        if t.due_date and not t.is_completed:
            cal_events.append({
                "date": t.due_date.isoformat(),
                "type": "task",
                "title": t.title,
                "priority": t.priority,
                "url": "/?view=tasks",
            })
    for p in db.query(Project).filter(Project.completion_date.isnot(None)).all():
        cal_events.append({
            "date": p.completion_date.isoformat(),
            "type": "deadline",
            "title": p.name,
            "url": f"/projects/{p.id}",
        })
    for df in db.query(DesignFile).filter(DesignFile.next_revision_date.isnot(None)).all():
        cal_events.append({
            "date": df.next_revision_date.isoformat(),
            "type": "revision",
            "title": df.original_filename,
            "url": f"/projects/{df.project_id}",
        })
    for sp in (
        db.query(SocialPost)
        .filter(SocialPost.scheduled_date.isnot(None), SocialPost.status == "scheduled")
        .all()
    ):
        cal_events.append({
            "date": sp.scheduled_date.isoformat(),
            "type": "social",
            "title": sp.caption[:60],
            "url": "/social",
        })

    # Yarn balance map — embedded in page so lookups are instant (no API calls)
    yarn_balance_map = {}
    for r in _color_stats(db):
        bal = int(r.opening_stock + r.total_in - r.total_out)
        yarn_balance_map[r.color_code] = {
            "balance": bal,
            "low": 0 < bal < LOW_STOCK_THRESHOLD,
            "out": bal <= 0,
        }

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "view": view,
            "today_iso": today.isoformat(),
            "stats": {
                "total_clients": total_clients,
                "active_projects": active_projects,
                "on_hold": on_hold,
                "completed": completed,
            },
            "stage_counts": stage_counts,
            "stage_labels": STAGE_LABELS,
            "recent_projects": recent_projects,
            "overdue_tasks": overdue_tasks,
            "today_tasks": today_tasks,
            "upcoming_tasks": upcoming_tasks,
            "no_due_tasks": no_due_tasks,
            "done_tasks": done_tasks,
            "active_projects_list": active_projects_list,
            "task_priority_labels": TASK_PRIORITY_LABELS,
            "task_priorities": TASK_PRIORITIES,
            "calendar_events_json": json.dumps(cal_events),
            "yarn_balance_map_json": json.dumps(yarn_balance_map),
        },
    )


# ── Client list ───────────────────────────────────────────────────────────────

@router.get("/contacts", response_class=HTMLResponse)
def clients_list(request: Request, q: str = "", db: Session = Depends(get_db)):
    query = db.query(Client)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Client.name.ilike(like)
            | Client.email.ilike(like)
            | Client.principal_architect_name.ilike(like)
            | Client.city.ilike(like)
        )
    clients = query.order_by(Client.name).all()
    return templates.TemplateResponse(
        request,
        "clients/list.html",
        {"request": request, "clients": clients, "q": q},
    )


# ── Create client ─────────────────────────────────────────────────────────────

@router.get("/contacts/new", response_class=HTMLResponse)
def clients_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "clients/form.html",
        {"request": request, "client": None, "indian_cities": INDIAN_CITIES},
    )


@router.post("/contacts/new")
def clients_create(
    request: Request,
    name: str = Form(...),
    email: str = Form(""),
    arch_name: List[str] = Form(default=[]),
    arch_numbers: List[str] = Form(default=[]),
    cp_name: List[str] = Form(default=[]),
    cp_number: List[str] = Form(default=[]),
    address: str = Form(""),
    city: str = Form(""),
    db: Session = Depends(get_db),
):
    architects = []
    for n, nums_str in zip(arch_name, arch_numbers):
        n = n.strip()
        if n:
            numbers = [x.strip() for x in nums_str.split(";") if x.strip()]
            architects.append({"name": n, "numbers": numbers})

    contact_persons = []
    for n, num in zip(cp_name, cp_number):
        n = n.strip()
        if n:
            contact_persons.append({"name": n, "number": num.strip()})

    first_arch = architects[0] if architects else {}
    first_cp = contact_persons[0] if contact_persons else {}

    client = Client(
        name=name.strip(),
        email=email.strip().lower() or None,
        principal_architects_json=json.dumps(architects, ensure_ascii=False) if architects else None,
        contact_persons_json=json.dumps(contact_persons, ensure_ascii=False) if contact_persons else None,
        principal_architect_name=first_arch.get("name") or None,
        principal_architect_numbers="; ".join(first_arch.get("numbers", [])) or None,
        contact_person_name=first_cp.get("name") or None,
        contact_person_number=first_cp.get("number") or None,
        address=address.strip() or None,
        city=city.strip() or None,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    if client.email:
        sync_contact(client.email, client.name)

    log_activity(db, request.session.get("user_name"), "Created contact",
                 entity_type="contact", entity_id=client.id, detail=client.name)
    return RedirectResponse(url=f"/contacts/{client.id}?success=Contact+created", status_code=303)


# ── Phonebook ─────────────────────────────────────────────────────────────────

@router.get("/phonebook", response_class=HTMLResponse)
def phonebook(request: Request, q: str = "", db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.name).all()
    entries = []
    for client in clients:
        for arch in client.principal_architects_list:
            entries.append({
                "name": arch["name"],
                "numbers": arch.get("numbers", []),
                "role": "Principal Architect",
                "studio_name": client.name,
                "studio_id": client.id,
                "city": client.city or "",
            })
        for cp in client.contact_persons_list:
            num = cp.get("number", "").strip()
            entries.append({
                "name": cp["name"],
                "numbers": [num] if num else [],
                "role": "Contact Person",
                "studio_name": client.name,
                "studio_id": client.id,
                "city": client.city or "",
            })

    if q:
        ql = q.lower()
        entries = [
            e for e in entries
            if ql in e["name"].lower()
            or ql in e["studio_name"].lower()
            or ql in e["city"].lower()
            or any(ql in n for n in e["numbers"])
        ]

    entries.sort(key=lambda e: e["name"].lower())
    return templates.TemplateResponse(
        request,
        "phonebook.html",
        {"request": request, "entries": entries, "q": q, "total": len(entries)},
    )


# ── Import clients ────────────────────────────────────────────────────────────

_IMPORT_COLUMNS = [
    "studio_name", "principal_architect_name", "principal_architect_numbers",
    "contact_person_name", "contact_person_number", "address", "city",
    "email", "notes",
]

_SAMPLE_ROWS = [
    ["Apex Design Studio", "Ravi Kumar", "+91 98765 43210; +91 87654 32109",
     "Priya Sharma", "+91 76543 21098", "123 MG Road", "Bengaluru",
     "ravi@apexdesign.com", "Met at design expo"],
    ["Urban Spaces LLP", "Meera Patel", "+91 99887 76655",
     "", "", "45 Linking Road", "Mumbai",
     "meera@urbanspaces.in", ""],
]


@router.get("/contacts/import", response_class=HTMLResponse)
def clients_import_form(request: Request):
    return templates.TemplateResponse(
        request,
        "clients/import.html", {"request": request, "results": None}
    )


@router.get("/contacts/import/template")
def clients_import_template():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_IMPORT_COLUMNS)
    writer.writerows(_SAMPLE_ROWS)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients_template.csv"},
    )


@router.post("/contacts/import", response_class=HTMLResponse)
async def clients_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # handles Excel BOM
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    imported, skipped = [], []

    for i, row in enumerate(reader, start=2):
        studio_name = (row.get("studio_name") or "").strip()
        if not studio_name:
            skipped.append({"row": i, "name": "(blank)", "reason": "Studio name is required"})
            continue

        if db.query(Client).filter(Client.name.ilike(studio_name)).first():
            skipped.append({"row": i, "name": studio_name, "reason": "Already exists"})
            continue

        raw_numbers = (row.get("principal_architect_numbers") or "").strip()
        numbers = [n.strip() for n in raw_numbers.split(";") if n.strip()]
        numbers_str = ", ".join(numbers) if numbers else None

        email = (row.get("email") or "").strip().lower() or None

        client = Client(
            name=studio_name,
            principal_architect_name=(row.get("principal_architect_name") or "").strip() or None,
            principal_architect_numbers=numbers_str,
            contact_person_name=(row.get("contact_person_name") or "").strip() or None,
            contact_person_number=(row.get("contact_person_number") or "").strip() or None,
            address=(row.get("address") or "").strip() or None,
            city=(row.get("city") or "").strip() or None,
            email=email,
            notes=(row.get("notes") or "").strip() or None,
        )
        db.add(client)
        db.commit()

        if email:
            sync_contact(email, studio_name)

        imported.append({"name": studio_name, "id": client.id})

    return templates.TemplateResponse(
        request,
        "clients/import.html",
        {"request": request, "results": {"imported": imported, "skipped": skipped}},
    )


# ── Client detail ─────────────────────────────────────────────────────────────

@router.get("/contacts/{client_id}", response_class=HTMLResponse)
def clients_detail(
    request: Request,
    client_id: int,
    sent: str = "",
    error_msg: str = "",
    success: str = "",
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return RedirectResponse(url="/contacts?error=Contact+not+found", status_code=303)

    recent_activities = (
        db.query(ClientActivity)
        .filter(ClientActivity.client_id == client_id)
        .order_by(ClientActivity.created_at.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "clients/detail.html",
        {
            "request": request,
            "client": client,
            "stage_labels": STAGE_LABELS,
            "activity_types": ACTIVITY_TYPES,
            "recent_activities": recent_activities,
            "sent": sent,
            "error_msg": error_msg,
            "success": success,
        },
    )


# ── Edit client ───────────────────────────────────────────────────────────────

@router.get("/contacts/{client_id}/edit", response_class=HTMLResponse)
def clients_edit_form(request: Request, client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return RedirectResponse(url="/contacts", status_code=303)
    return templates.TemplateResponse(
        request,
        "clients/form.html",
        {"request": request, "client": client, "indian_cities": INDIAN_CITIES},
    )


@router.post("/contacts/{client_id}/edit")
def clients_update(
    request: Request,
    client_id: int,
    name: str = Form(...),
    email: str = Form(""),
    arch_name: List[str] = Form(default=[]),
    arch_numbers: List[str] = Form(default=[]),
    cp_name: List[str] = Form(default=[]),
    cp_number: List[str] = Form(default=[]),
    address: str = Form(""),
    city: str = Form(""),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return RedirectResponse(url="/contacts", status_code=303)

    architects = []
    for n, nums_str in zip(arch_name, arch_numbers):
        n = n.strip()
        if n:
            numbers = [x.strip() for x in nums_str.split(";") if x.strip()]
            architects.append({"name": n, "numbers": numbers})

    contact_persons = []
    for n, num in zip(cp_name, cp_number):
        n = n.strip()
        if n:
            contact_persons.append({"name": n, "number": num.strip()})

    first_arch = architects[0] if architects else {}
    first_cp = contact_persons[0] if contact_persons else {}

    client.name = name.strip()
    client.email = email.strip().lower() or None
    client.principal_architects_json = json.dumps(architects, ensure_ascii=False) if architects else None
    client.contact_persons_json = json.dumps(contact_persons, ensure_ascii=False) if contact_persons else None
    client.principal_architect_name = first_arch.get("name") or None
    client.principal_architect_numbers = "; ".join(first_arch.get("numbers", [])) or None
    client.contact_person_name = first_cp.get("name") or None
    client.contact_person_number = first_cp.get("number") or None
    client.address = address.strip() or None
    client.city = city.strip() or None
    db.commit()

    if client.email:
        sync_contact(client.email, client.name)

    log_activity(db, request.session.get("user_name"), "Updated contact",
                 entity_type="contact", entity_id=client_id, detail=client.name)
    return RedirectResponse(url=f"/contacts/{client_id}?success=Contact+updated", status_code=303)


# ── Delete client ─────────────────────────────────────────────────────────────

@router.post("/contacts/{client_id}/delete")
def clients_delete(request: Request, client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        name = client.name
        db.delete(client)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted contact",
                     entity_type="contact", detail=name)
    return RedirectResponse(url="/contacts?success=Contact+deleted", status_code=303)


# ── Activities ─────────────────────────────────────────────────────────────────

@router.post("/contacts/{client_id}/activities")
def add_activity(
    request: Request,
    client_id: int,
    activity_type: str = Form(...),
    note: str = Form(""),
    scheduled_at: str = Form(""),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return RedirectResponse(url="/contacts", status_code=303)

    from datetime import datetime as _dt
    sched = None
    if scheduled_at.strip():
        try:
            sched = _dt.fromisoformat(scheduled_at)
        except ValueError:
            pass

    if activity_type not in ACTIVITY_TYPES:
        activity_type = "note"

    db.add(ClientActivity(
        client_id=client_id,
        activity_type=activity_type,
        note=note.strip() or None,
        scheduled_at=sched,
        logged_by_name=request.session.get("user_name") or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/contacts/{client_id}?success=Activity+logged", status_code=303)


@router.post("/contacts/{client_id}/activities/{activity_id}/complete")
def complete_activity(client_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(ClientActivity).filter(
        ClientActivity.id == activity_id,
        ClientActivity.client_id == client_id,
    ).first()
    if activity:
        activity.is_completed = True
        db.commit()
    return RedirectResponse(url=f"/contacts/{client_id}", status_code=303)


@router.post("/contacts/{client_id}/activities/{activity_id}/revert")
def revert_activity(client_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(ClientActivity).filter(
        ClientActivity.id == activity_id,
        ClientActivity.client_id == client_id,
    ).first()
    if activity:
        activity.is_completed = False
        db.commit()
    return RedirectResponse(url=f"/contacts/{client_id}", status_code=303)


@router.post("/contacts/{client_id}/activities/{activity_id}/delete")
def delete_activity(client_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(ClientActivity).filter(
        ClientActivity.id == activity_id,
        ClientActivity.client_id == client_id,
    ).first()
    if activity:
        db.delete(activity)
        db.commit()
    return RedirectResponse(url=f"/contacts/{client_id}", status_code=303)
