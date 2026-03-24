from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.lead import (
    Lead, LeadActivity, LeadStageHistory,
    LEAD_STAGES, LEAD_STAGE_LABELS, LEAD_SOURCES, LEAD_ACTIVITY_TYPES,
)
from app.templates_config import templates

router = APIRouter(prefix="/leads")


# ── Pipeline (Kanban) ─────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def leads_pipeline(request: Request, db: Session = Depends(get_db)):
    all_leads = db.query(Lead).order_by(Lead.updated_at.desc()).all()
    by_stage = {stage: [] for stage in LEAD_STAGES}
    for lead in all_leads:
        if lead.stage in by_stage:
            by_stage[lead.stage].append(lead)

    return templates.TemplateResponse(
        request,
        "leads/pipeline.html",
        {
            "request": request,
            "by_stage": by_stage,
            "stages": LEAD_STAGES,
            "stage_labels": LEAD_STAGE_LABELS,
            "lead_sources": LEAD_SOURCES,
            "total": len(all_leads),
        },
    )


# ── Lead detail ───────────────────────────────────────────────────────────────

@router.get("/{lead_id}", response_class=HTMLResponse)
def lead_detail(
    request: Request,
    lead_id: int,
    success: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return RedirectResponse(url="/leads", status_code=303)

    activities = (
        db.query(LeadActivity)
        .filter(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.created_at.desc())
        .all()
    )
    history = (
        db.query(LeadStageHistory)
        .filter(LeadStageHistory.lead_id == lead_id)
        .order_by(LeadStageHistory.changed_at)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "leads/detail.html",
        {
            "request": request,
            "lead": lead,
            "activities": activities,
            "history": history,
            "stages": LEAD_STAGES,
            "stage_labels": LEAD_STAGE_LABELS,
            "lead_sources": LEAD_SOURCES,
            "activity_types": LEAD_ACTIVITY_TYPES,
            "success": success,
            "error": error,
        },
    )


# ── Update lead info ──────────────────────────────────────────────────────────

@router.post("/{lead_id}/update")
def lead_update(
    lead_id: int,
    source: str = Form("other"),
    requirements: str = Form(""),
    budget: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return RedirectResponse(url="/leads", status_code=303)

    lead.source = source
    lead.requirements = requirements.strip() or None
    lead.notes = notes.strip() or None
    try:
        lead.budget = float(budget) if budget.strip() else None
    except ValueError:
        lead.budget = None
    db.commit()

    return RedirectResponse(url=f"/leads/{lead_id}?success=Lead+updated", status_code=303)


# ── Stage transition ──────────────────────────────────────────────────────────

@router.post("/{lead_id}/stage")
def lead_set_stage(
    lead_id: int,
    stage: str = Form(...),
    note: str = Form(""),
    lost_reason: str = Form(""),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead or stage not in LEAD_STAGES:
        return RedirectResponse(url=f"/leads/{lead_id}", status_code=303)

    from_stage = lead.stage
    lead.stage = stage
    if stage == "lost" and lost_reason.strip():
        lead.lost_reason = lost_reason.strip()

    db.add(LeadStageHistory(
        lead_id=lead_id,
        from_stage=from_stage,
        to_stage=stage,
        note=note.strip() or None,
    ))
    db.commit()

    return RedirectResponse(url=f"/leads/{lead_id}?success=Stage+updated", status_code=303)


# ── Add activity ──────────────────────────────────────────────────────────────

@router.post("/{lead_id}/activities")
def add_activity(
    lead_id: int,
    activity_type: str = Form(...),
    note: str = Form(""),
    scheduled_at: str = Form(""),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return RedirectResponse(url="/leads", status_code=303)

    sched = None
    if scheduled_at.strip():
        try:
            sched = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass

    db.add(LeadActivity(
        lead_id=lead_id,
        activity_type=activity_type,
        note=note.strip() or None,
        scheduled_at=sched,
    ))
    db.commit()

    return RedirectResponse(url=f"/leads/{lead_id}?success=Activity+logged", status_code=303)


# ── Mark activity complete ────────────────────────────────────────────────────

@router.post("/{lead_id}/activities/{activity_id}/complete")
def complete_activity(lead_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(LeadActivity).filter(
        LeadActivity.id == activity_id, LeadActivity.lead_id == lead_id
    ).first()
    if activity:
        activity.is_completed = True
        db.commit()
    return RedirectResponse(url=f"/leads/{lead_id}", status_code=303)


# ── Delete activity ───────────────────────────────────────────────────────────

@router.post("/{lead_id}/activities/{activity_id}/delete")
def delete_activity(lead_id: int, activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(LeadActivity).filter(
        LeadActivity.id == activity_id, LeadActivity.lead_id == lead_id
    ).first()
    if activity:
        db.delete(activity)
        db.commit()
    return RedirectResponse(url=f"/leads/{lead_id}", status_code=303)
