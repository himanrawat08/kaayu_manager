from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.design import DesignRevision
from app.models.project import Project

router = APIRouter(prefix="/projects")


@router.post("/{project_id}/revisions/add")
def add_revision(
    project_id: int,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    max_rev = (
        db.query(func.max(DesignRevision.revision_number))
        .filter(DesignRevision.project_id == project_id)
        .scalar()
    ) or 0

    rev = DesignRevision(
        project_id=project_id,
        revision_number=max_rev + 1,
        title=title.strip(),
        description=description.strip() or None,
        status="in_progress",
    )
    db.add(rev)
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}#rev-{rev.id}", status_code=303)


@router.post("/{project_id}/revisions/{revision_id}/edit")
def edit_revision(
    project_id: int,
    revision_id: int,
    title: str = Form(...),
    description: str = Form(""),
    feedback_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    rev = db.query(DesignRevision).filter(
        DesignRevision.id == revision_id, DesignRevision.project_id == project_id
    ).first()
    if rev:
        rev.title = title.strip()
        rev.description = description.strip() or None
        rev.feedback_notes = feedback_notes.strip() or None
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/revisions/{revision_id}/status")
def revision_status(
    project_id: int,
    revision_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    rev = db.query(DesignRevision).filter(
        DesignRevision.id == revision_id, DesignRevision.project_id == project_id
    ).first()
    if rev and status in ("in_progress", "approved", "rejected"):
        rev.status = status
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/revisions/{revision_id}/delete")
def delete_revision(project_id: int, revision_id: int, db: Session = Depends(get_db)):
    rev = db.query(DesignRevision).filter(
        DesignRevision.id == revision_id, DesignRevision.project_id == project_id
    ).first()
    if rev:
        db.delete(rev)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
