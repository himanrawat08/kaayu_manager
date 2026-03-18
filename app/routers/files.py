import logging
import uuid
from pathlib import Path

import httpx

from app.utils.time import now_ist

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.project import Project
from app.models.project_files import (
    DesignFile, DesignFileFeedback, ProductionFile, ProjectBriefFile,
    PRODUCTION_FILE_CATEGORIES,
)
from app.services import storage

router = APIRouter(prefix="/projects")

# Allowed file extensions for uploads (case-insensitive)
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".dxf", ".dwg", ".ai", ".eps", ".psd",
    ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt",
    ".zip", ".rar", ".7z",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _save(file: UploadFile, subdir: str, project_id: int) -> tuple[str, str, int]:
    """Upload file to Supabase Storage. Returns (storage_path, original_filename, size_bytes).
    Raises HTTPException on invalid extension or file too large."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    chunks = []
    size = 0
    while chunk := file.file.read(256 * 1024):  # 256 KB chunks
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds the 50 MB size limit.")
        chunks.append(chunk)

    data = b"".join(chunks)
    stored_name = uuid.uuid4().hex + ext
    path = f"{subdir}/{project_id}/{stored_name}"
    storage.upload(path, data, file.filename or stored_name)

    return path, file.filename, size


def _remove_file(stored_path: str) -> None:
    storage.delete(stored_path)


# ── Project Brief Files ────────────────────────────────────────────────────────

@router.post("/{project_id}/brief-files/upload")
def upload_brief_file(
    project_id: int,
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)
    if project.current_stage != "design":
        return RedirectResponse(
            url=f"/projects/{project_id}?error=Brief+files+can+only+be+uploaded+during+the+Design+stage",
            status_code=303,
        )

    try:
        stored, original, size = _save(file, "briefs", project_id)
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.exception("Storage timeout uploading brief file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?error=Upload+timed+out.+Try+a+smaller+file+or+try+again.",
            status_code=303,
        )
    except Exception:
        logger.exception("Storage error uploading brief file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?error=File+upload+failed.+Please+try+again.",
            status_code=303,
        )
    db.add(ProjectBriefFile(
        project_id=project_id,
        original_filename=original,
        stored_filename=stored,
        description=description.strip() or None,
        file_size=size,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?success=File+uploaded", status_code=303)


@router.post("/{project_id}/brief-files/{file_id}/delete")
def delete_brief_file(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(ProjectBriefFile).filter(
        ProjectBriefFile.id == file_id, ProjectBriefFile.project_id == project_id
    ).first()
    if f:
        _remove_file(f.stored_filename)
        db.delete(f)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


# ── Design Files ───────────────────────────────────────────────────────────────

@router.post("/{project_id}/design-files/upload")
def upload_design_file(
    project_id: int,
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(url="/projects", status_code=303)

    try:
        stored, original, size = _save(file, "design", project_id)
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.exception("Storage timeout uploading design file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?error=Upload+timed+out.+Try+a+smaller+file+or+try+again.",
            status_code=303,
        )
    except Exception:
        logger.exception("Storage error uploading design file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?error=File+upload+failed.+Please+try+again.",
            status_code=303,
        )
    db.add(DesignFile(
        project_id=project_id,
        original_filename=original,
        stored_filename=stored,
        description=description.strip() or None,
        file_size=size,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?success=Design+file+uploaded", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/edit")
def edit_design_file(
    project_id: int,
    file_id: int,
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f:
        f.description = description.strip() or None
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/mark-sent")
def mark_design_sent(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f and not f.sent_at:
        f.sent_at = now_ist()
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/feedback/add")
def add_design_feedback(
    project_id: int,
    file_id: int,
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f and note.strip():
        db.add(DesignFileFeedback(design_file_id=file_id, note=note.strip()))
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/feedback/{fb_id}/delete")
def delete_design_feedback(
    project_id: int,
    file_id: int,
    fb_id: int,
    db: Session = Depends(get_db),
):
    fb = db.query(DesignFileFeedback).filter(
        DesignFileFeedback.id == fb_id,
        DesignFileFeedback.design_file_id == file_id,
    ).first()
    if fb:
        db.delete(fb)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/revision-date")
def set_revision_date(
    project_id: int,
    file_id: int,
    next_revision_date: str = Form(""),
    db: Session = Depends(get_db),
):
    from datetime import date as date_type
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f:
        if next_revision_date.strip():
            try:
                f.next_revision_date = date_type.fromisoformat(next_revision_date.strip())
            except ValueError:
                pass
        else:
            f.next_revision_date = None
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/mark-final")
def mark_design_final(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f:
        f.is_final = not f.is_final  # toggle
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@router.post("/{project_id}/design-files/{file_id}/delete")
def delete_design_file(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(DesignFile).filter(
        DesignFile.id == file_id, DesignFile.project_id == project_id
    ).first()
    if f:
        _remove_file(f.stored_filename)
        db.delete(f)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


# ── Production Files ───────────────────────────────────────────────────────────

@router.post("/{project_id}/production-files/upload")
def upload_production_file(
    project_id: int,
    file_category: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    # Gate: require at least one final design file
    has_final = db.query(DesignFile).filter(
        DesignFile.project_id == project_id, DesignFile.is_final == True  # noqa: E712
    ).first()
    if not has_final:
        return RedirectResponse(
            url=f"/projects/{project_id}?error=Mark+a+design+file+as+final+first",
            status_code=303,
        )

    if file_category not in PRODUCTION_FILE_CATEGORIES:
        return RedirectResponse(url=f"/projects/{project_id}?error=Invalid+file+category", status_code=303)

    try:
        stored, original, size = _save(file, "production", project_id)
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.exception("Storage timeout uploading production file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?tab=production&error=Upload+timed+out.+Try+a+smaller+file+or+try+again.",
            status_code=303,
        )
    except Exception:
        logger.exception("Storage error uploading production file for project %s", project_id)
        return RedirectResponse(
            url=f"/projects/{project_id}?tab=production&error=File+upload+failed.+Please+try+again.",
            status_code=303,
        )
    db.add(ProductionFile(
        project_id=project_id,
        file_category=file_category,
        original_filename=original,
        stored_filename=stored,
        description=description.strip() or None,
        file_size=size,
    ))
    db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?tab=production&success=Production+file+uploaded", status_code=303)


@router.post("/{project_id}/production-files/{file_id}/edit")
def edit_production_file(
    project_id: int,
    file_id: int,
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    f = db.query(ProductionFile).filter(
        ProductionFile.id == file_id, ProductionFile.project_id == project_id
    ).first()
    if f:
        f.description = description.strip() or None
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?tab=production", status_code=303)


@router.post("/{project_id}/production-files/{file_id}/mark-sent")
def mark_production_sent(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(ProductionFile).filter(
        ProductionFile.id == file_id, ProductionFile.project_id == project_id
    ).first()
    if f and not f.sent_at:
        f.sent_at = now_ist()
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?tab=production", status_code=303)


@router.post("/{project_id}/production-files/{file_id}/delete")
def delete_production_file(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.query(ProductionFile).filter(
        ProductionFile.id == file_id, ProductionFile.project_id == project_id
    ).first()
    if f:
        _remove_file(f.stored_filename)
        db.delete(f)
        db.commit()
    return RedirectResponse(url=f"/projects/{project_id}?tab=production", status_code=303)
