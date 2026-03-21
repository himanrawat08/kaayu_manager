import shutil
from datetime import date, datetime

from app.utils.time import now_ist
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.project import Project, StageLog, STAGES, STAGE_LABELS
from app.models.activity import ProjectActivity, ACTIVITY_TYPES
from app.models.project_files import DesignFile, PRODUCTION_FILE_CATEGORIES
from app.services.log_activity import log_activity
from app.services import storage

router = APIRouter(prefix="/projects")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["storage_url"] = storage.public_url


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def projects_list(
    request: Request,
    stage: str = "",
    status: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Project)
    if stage:
        query = query.filter(Project.current_stage == stage)
    if status:
        query = query.filter(Project.status == status)
    projects = query.order_by(Project.updated_at.desc()).all()
    return templates.TemplateResponse(
        "projects/list.html",
        {
            "request": request,
            "projects": projects,
            "stage_labels": STAGE_LABELS,
            "stage_filter": stage,
            "status_filter": status,
        },
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
def projects_new_form(request: Request, client_id: int = None, db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.name).all()
    prefill_client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    return templates.TemplateResponse(
        "projects/form.html",
        {"request": request, "project": None, "clients": clients, "prefill_client": prefill_client},
    )


@router.post("/new")
def projects_create(
    request: Request,
    client_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    completion_date: str = Form(""),
    project_contact_name: str = Form(""),
    project_contact_phone: str = Form(""),
    db: Session = Depends(get_db),
):
    comp_date = None
    if completion_date.strip():
        try:
            comp_date = date.fromisoformat(completion_date.strip())
        except ValueError:
            pass

    project = Project(
        client_id=client_id,
        name=name.strip(),
        description=description.strip() or None,
        completion_date=comp_date,
        project_contact_name=project_contact_name.strip() or None,
        project_contact_phone=project_contact_phone.strip() or None,
        current_stage="design",
        status="active",
    )
    db.add(project)
    db.flush()

    log = StageLog(project_id=project.id, stage="design", started_at=now_ist())
    db.add(log)
    db.commit()
    db.refresh(project)

    log_activity(db, request.session.get("user_name"), "Created project",
                 entity_type="project", entity_id=project.id, detail=project.name)
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{project_id}", response_class=HTMLResponse)
def projects_detail(
    request: Request,
    project_id: int,
    sent: str = "",
    error_msg: str = "",
    success: str = "",
    error: str = "",
    tab: str = "design",
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects?error=Project+not+found", status_code=303)

    current_log = (
        db.query(StageLog)
        .filter(StageLog.project_id == project_id, StageLog.stage == project.current_stage)
        .order_by(StageLog.created_at.desc())
        .first()
    )

    has_final_design = any(f.is_final for f in project.design_files)
    show_design_section = (
        project.current_stage == "design"
        or bool(project.design_files)
        or bool(project.production_files)
    )

    recent_project_activities = (
        db.query(ProjectActivity)
        .filter(ProjectActivity.project_id == project_id)
        .order_by(ProjectActivity.created_at.desc())
        .limit(30)
        .all()
    )

    return templates.TemplateResponse(
        "projects/detail.html",
        {
            "request": request,
            "project": project,
            "stages": STAGES,
            "stage_labels": STAGE_LABELS,
            "current_log": current_log,
            "has_final_design": has_final_design,
            "show_design_section": show_design_section,
            "production_file_categories": PRODUCTION_FILE_CATEGORIES,
            "active_tab": tab,
            "sent": sent,
            "error_msg": error_msg or error,
            "success": success,
            "activity_types": ACTIVITY_TYPES,
            "recent_project_activities": recent_project_activities,
        },
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/edit", response_class=HTMLResponse)
def projects_edit_form(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)
    clients = db.query(Client).order_by(Client.name).all()
    return templates.TemplateResponse(
        "projects/form.html",
        {"request": request, "project": project, "clients": clients, "prefill_client": None},
    )


@router.post("/{project_id}/edit")
def projects_update(
    request: Request,
    project_id: int,
    client_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    status: str = Form("active"),
    completion_date: str = Form(""),
    project_contact_name: str = Form(""),
    project_contact_phone: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    comp_date = None
    if completion_date.strip():
        try:
            comp_date = date.fromisoformat(completion_date.strip())
        except ValueError:
            pass

    project.client_id = client_id
    project.name = name.strip()
    project.description = description.strip() or None
    project.status = status
    project.completion_date = comp_date
    project.project_contact_name = project_contact_name.strip() or None
    project.project_contact_phone = project_contact_phone.strip() or None
    db.commit()
    log_activity(db, request.session.get("user_name"), "Updated project",
                 entity_type="project", entity_id=project_id, detail=project.name)
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/delete")
def projects_delete(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        name = project.name
        # Clean up uploaded files from Supabase Storage
        all_stored_paths = (
            [f.stored_filename for f in project.brief_files]
            + [f.stored_filename for f in project.design_files]
            + [f.stored_filename for f in project.production_files]
        )
        db.delete(project)
        db.commit()
        for path in all_stored_paths:
            storage.delete(path)
        log_activity(db, request.session.get("user_name"), "Deleted project",
                     entity_type="project", detail=name)
    return RedirectResponse(url="/projects?success=Project+deleted", status_code=303)


# ── Stage transitions ─────────────────────────────────────────────────────────

@router.post("/{project_id}/advance-stage")
def advance_stage(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or project.current_stage == "completed":
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    current_idx = STAGES.index(project.current_stage)
    if current_idx + 1 >= len(STAGES):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    current_log = (
        db.query(StageLog)
        .filter(StageLog.project_id == project_id, StageLog.stage == project.current_stage)
        .order_by(StageLog.created_at.desc())
        .first()
    )
    if current_log and not current_log.completed_at:
        current_log.completed_at = now_ist()

    next_stage = STAGES[current_idx + 1]
    project.current_stage = next_stage
    db.add(StageLog(project_id=project_id, stage=next_stage, started_at=now_ist()))
    db.commit()

    log_activity(db, request.session.get("user_name"), f"Advanced stage to {STAGE_LABELS[next_stage]}",
                 entity_type="project", entity_id=project_id, detail=project.name)
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/set-stage")
def set_stage(project_id: int, stage: str = Form(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or stage not in STAGES:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    project.current_stage = stage
    db.add(StageLog(project_id=project_id, stage=stage, started_at=now_ist()))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/stage-notes")
def stage_notes(project_id: int, notes: str = Form(""), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    log = (
        db.query(StageLog)
        .filter(StageLog.project_id == project_id, StageLog.stage == project.current_stage)
        .order_by(StageLog.created_at.desc())
        .first()
    )
    if log:
        log.notes = notes.strip() or None
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


# ── Project Activities (User Log) ─────────────────────────────────────────────

@router.post("/{project_id}/activities")
def project_add_activity(
    request: Request,
    project_id: int,
    activity_type: str = Form(...),
    note: str = Form(""),
    scheduled_at: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    sched = None
    if scheduled_at.strip():
        try:
            sched = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass

    if activity_type not in ACTIVITY_TYPES:
        activity_type = "note"

    db.add(ProjectActivity(
        project_id=project_id,
        activity_type=activity_type,
        note=note.strip() or None,
        scheduled_at=sched,
        logged_by_name=request.session.get("user_name") or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?success=Activity+logged", status_code=303)


@router.post("/{project_id}/activities/{activity_id}/complete")
def project_complete_activity(project_id: int, activity_id: int, db: Session = Depends(get_db)):
    act = db.query(ProjectActivity).filter(
        ProjectActivity.id == activity_id,
        ProjectActivity.project_id == project_id,
    ).first()
    if act:
        act.is_completed = True
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/activities/{activity_id}/revert")
def project_revert_activity(project_id: int, activity_id: int, db: Session = Depends(get_db)):
    act = db.query(ProjectActivity).filter(
        ProjectActivity.id == activity_id,
        ProjectActivity.project_id == project_id,
    ).first()
    if act:
        act.is_completed = False
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.get("/{project_id}/production-sheet", response_class=HTMLResponse)
def production_sheet(request: Request, project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    production_log = (
        db.query(StageLog)
        .filter(StageLog.project_id == project_id, StageLog.stage == "production")
        .order_by(StageLog.created_at.asc())
        .first()
    )
    final_design = next((f for f in project.design_files if f.is_final), None)

    return templates.TemplateResponse(
        "projects/production_sheet.html",
        {
            "request": request,
            "project": project,
            "production_log": production_log,
            "final_design": final_design,
        },
    )


@router.post("/{project_id}/activities/{activity_id}/delete")
def project_delete_activity(project_id: int, activity_id: int, db: Session = Depends(get_db)):
    act = db.query(ProjectActivity).filter(
        ProjectActivity.id == activity_id,
        ProjectActivity.project_id == project_id,
    ).first()
    if act:
        db.delete(act)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
