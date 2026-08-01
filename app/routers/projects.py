import shutil
from datetime import date, datetime

from app.utils.time import now_ist
from pathlib import Path

import httpx
import fitz  # PyMuPDF

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.quotation import Quotation
from app.models.project import (
    Project, StageLog, ProjectMilestone,
    STAGES, STAGE_LABELS, MILESTONE_TYPES,
    SALES_FLOW_STAGES, SALES_OUTCOME_STAGES, SALES_STAGES, PRODUCTION_STAGES,
    STAGE_ADVANCE_MAP,
)
from app.models.activity import ProjectActivity, ACTIVITY_TYPES
from app.models.project_files import DesignFile, PRODUCTION_FILE_CATEGORIES
from app.models.yarn import YarnTransaction
from app.models.job_card import JobCard
from app.services.log_activity import log_activity
from app.services import storage
from app.templates_config import templates

router = APIRouter(prefix="/projects")


def _sync_project_status(project) -> None:
    """Update project.status based on current_stage and quote statuses."""
    if project.current_stage == "completed":
        project.status = "completed"
        return
    if project.current_stage == "lost":
        project.status = "lost"
        return
    quotes = project.quotations
    if not quotes:
        project.status = "active"
        return
    if any(q.status == "accepted" for q in quotes):
        project.status = "active"
    elif any(q.status == "on_hold" for q in quotes):
        project.status = "on_hold"
    elif any(q.status in ("draft", "sent") for q in quotes):
        project.status = "active"
    else:
        project.status = "lost"


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
    active_projects = [p for p in projects if p.status in ("active", "on_hold")]
    closed_projects = [p for p in projects if p.status in ("completed", "lost")]
    return templates.TemplateResponse(
        request,
        "projects/list.html",
        {
            "request": request,
            "projects": projects,
            "active_projects": active_projects,
            "closed_projects": closed_projects,
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
        request,
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
        current_stage="preliminary_design",
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
        project.current_stage in PRODUCTION_STAGES
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

    yarn_transactions = (
        db.query(YarnTransaction)
        .filter(YarnTransaction.project_id == project_id)
        .order_by(YarnTransaction.date.desc(), YarnTransaction.id.desc())
        .all()
    )

    job_cards = (
        db.query(JobCard)
        .filter(JobCard.project_id == project_id)
        .order_by(JobCard.id.desc())
        .all()
    )

    milestones = project.milestones  # ordered by occurred_at
    milestone_deltas = [None]
    for i in range(1, len(milestones)):
        delta = (milestones[i].occurred_at - milestones[i - 1].occurred_at).days
        milestone_deltas.append(delta)

    return templates.TemplateResponse(
        request,
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
            "sales_flow_stages": SALES_FLOW_STAGES,
            "sales_outcome_stages": SALES_OUTCOME_STAGES,
            "sales_stages": SALES_STAGES,
            "production_stages": PRODUCTION_STAGES,
            "stage_advance_map": STAGE_ADVANCE_MAP,
            "sent": sent,
            "error_msg": error_msg or error,
            "success": success,
            "activity_types": ACTIVITY_TYPES,
            "recent_project_activities": recent_project_activities,
            "yarn_transactions": yarn_transactions,
            "job_cards": job_cards,
            "milestones": milestones,
            "milestone_deltas": milestone_deltas,
            "milestone_types": MILESTONE_TYPES,
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
        request,
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
    if not project or project.current_stage not in STAGE_ADVANCE_MAP:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    current_log = (
        db.query(StageLog)
        .filter(StageLog.project_id == project_id, StageLog.stage == project.current_stage)
        .order_by(StageLog.created_at.desc())
        .first()
    )
    if current_log and not current_log.completed_at:
        current_log.completed_at = now_ist()

    next_stage = STAGE_ADVANCE_MAP[project.current_stage]
    project.current_stage = next_stage
    _sync_project_status(project)
    db.add(StageLog(project_id=project_id, stage=next_stage, started_at=now_ist()))
    db.commit()

    # Auto-milestone for key production stages (only if none exists yet)
    if next_stage in ("polish", "production"):
        existing = db.query(ProjectMilestone).filter(
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.milestone_type == next_stage,
        ).first()
        if not existing:
            db.add(ProjectMilestone(project_id=project_id, milestone_type=next_stage))
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
    _sync_project_status(project)
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
    final_design_is_pdf = (
        final_design and final_design.original_filename.lower().endswith(".pdf")
    )

    return templates.TemplateResponse(
        request,
        "projects/production_sheet.html",
        {
            "request": request,
            "project": project,
            "production_log": production_log,
            "final_design": final_design,
            "final_design_is_pdf": final_design_is_pdf,
        },
    )


@router.post("/{project_id}/production-details")
def save_production_details(
    project_id: int,
    prod_design_name: str = Form(""),
    prod_size: str = Form(""),
    prod_polish_stain: str = Form(""),
    prod_polish_type: str = Form(""),
    prod_veneer_type: str = Form(""),
    prod_design_page: int = Form(1),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)
    project.prod_design_name = prod_design_name.strip() or None
    project.prod_size = prod_size.strip() or None
    project.prod_polish_stain = prod_polish_stain.strip() or None
    project.prod_polish_type = prod_polish_type.strip() or None
    project.prod_veneer_type = prod_veneer_type.strip() or None
    project.prod_design_page = max(1, prod_design_page)
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?success=Production+details+saved", status_code=303)


@router.get("/{project_id}/design-preview.png")
def design_preview_png(project_id: int, page: int = 1, db: Session = Depends(get_db)):
    """Render a page of the final design PDF as PNG for use in the production sheet."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return Response(status_code=404)
    final_design = next((f for f in project.design_files if f.is_final), None)
    if not final_design or not final_design.original_filename.lower().endswith(".pdf"):
        return Response(status_code=404)
    try:
        url = storage.public_url(final_design.stored_filename)
        pdf_bytes = httpx.get(url, timeout=30).content
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_idx = min(max(page - 1, 0), doc.page_count - 1)
        mat = fitz.Matrix(2, 2)
        pix = doc[page_idx].get_pixmap(matrix=mat)
        return Response(content=pix.tobytes("png"), media_type="image/png")
    except Exception:
        return Response(status_code=500)


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


# ── Design Milestones ─────────────────────────────────────────────────────────

@router.post("/{project_id}/milestones")
def add_milestone(
    project_id: int,
    milestone_type: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    if milestone_type not in MILESTONE_TYPES:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    revision_number = None
    if milestone_type == "concept_board_revision":
        existing_revs = db.query(ProjectMilestone).filter(
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.milestone_type == "concept_board_revision",
        ).all()
        revision_number = max((r.revision_number or 0 for r in existing_revs), default=0) + 1

    db.add(ProjectMilestone(
        project_id=project_id,
        milestone_type=milestone_type,
        revision_number=revision_number,
        notes=notes.strip() or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?success=Milestone+logged", status_code=303)


@router.post("/{project_id}/milestones/{milestone_id}/delete")
def delete_milestone(project_id: int, milestone_id: int, db: Session = Depends(get_db)):
    m = db.query(ProjectMilestone).filter(
        ProjectMilestone.id == milestone_id,
        ProjectMilestone.project_id == project_id,
    ).first()
    if m:
        db.delete(m)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
