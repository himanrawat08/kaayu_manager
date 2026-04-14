import uuid
from datetime import date
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import nulls_last, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.project import Project
from app.models.task import (
    NOTE_TYPE_LABELS,
    NOTE_TYPES,
    TASK_DEPARTMENTS,
    TASK_PRIORITIES,
    TASK_PRIORITY_LABELS,
    TASK_STATUS_LABELS,
    TASK_STATUSES,
    SubTask,
    Task,
    TaskFile,
    TaskNote,
)
from app.models.user import User
from app.services import storage
from app.services.log_activity import log_activity
from app.templates_config import templates

router = APIRouter(prefix="/tasks")

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".dxf", ".dwg", ".ai", ".eps", ".psd",
    ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt",
    ".zip", ".rar", ".7z",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _save_task_file(file: UploadFile, task_id: int) -> tuple[str, str, int]:
    """Upload file to storage. Returns (stored_path, original_filename, size_bytes)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{ext}' not allowed.")
    chunks = []
    size = 0
    while chunk := file.file.read(256 * 1024):
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise ValueError("File exceeds 50 MB limit.")
        chunks.append(chunk)
    data = b"".join(chunks)
    stored_name = uuid.uuid4().hex + ext
    path = f"task-files/{task_id}/{stored_name}"
    storage.upload(path, data, file.filename or stored_name)
    return path, file.filename or stored_name, size


def _assigned_names(assigned_to: List[str]) -> str | None:
    """Join selected names, strip blanks, return None if empty."""
    names = [n.strip() for n in assigned_to if n.strip()]
    return ",".join(names) if names else None


def _get_users(db: Session) -> list:
    return db.query(User).filter(User.is_active == True).order_by(User.full_name).all()  # noqa: E712


def _is_admin(request: Request) -> bool:
    return request.session.get("user_role", "") in ("admin", "super_admin")


@router.get("", response_class=HTMLResponse)
def tasks_list(
    request: Request,
    department: str = "",
    status: str = "",
    priority: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Task).options(joinedload(Task.project))
    if department:
        query = query.filter(Task.department == department)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if q:
        query = query.filter(Task.title.ilike(f"%{q.strip()}%"))

    # Non-admins only see tasks they are assigned to
    if not _is_admin(request):
        user_name = request.session.get("user_name", "")
        query = query.filter(
            or_(
                Task.assigned_to == user_name,
                Task.assigned_to.like(f"{user_name},%"),
                Task.assigned_to.like(f"%,{user_name}"),
                Task.assigned_to.like(f"%,{user_name},%"),
            )
        )

    tasks = query.order_by(nulls_last(Task.due_date.asc()), Task.created_at.desc()).all()

    # Summary counts (unfiltered for admins, filtered for non-admins)
    count_query = db.query(Task.status)
    if not _is_admin(request):
        user_name = request.session.get("user_name", "")
        count_query = count_query.filter(
            or_(
                Task.assigned_to == user_name,
                Task.assigned_to.like(f"{user_name},%"),
                Task.assigned_to.like(f"%,{user_name}"),
                Task.assigned_to.like(f"%,{user_name},%"),
            )
        )
    all_tasks = count_query.all()
    counts = {s: sum(1 for (t,) in all_tasks if t == s) for s in TASK_STATUSES}
    counts["total"] = len(all_tasks)

    return templates.TemplateResponse(
        request,
        "tasks/list.html",
        {
            "request": request,
            "tasks": tasks,
            "counts": counts,
            "departments": TASK_DEPARTMENTS,
            "statuses": TASK_STATUSES,
            "status_labels": TASK_STATUS_LABELS,
            "priorities": TASK_PRIORITIES,
            "priority_labels": TASK_PRIORITY_LABELS,
            "dept_filter": department,
            "status_filter": status,
            "priority_filter": priority,
            "q": q,
            "today": date.today(),
        },
    )


@router.get("/new", response_class=HTMLResponse)
def tasks_new_form(request: Request, db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.name).all()
    users = _get_users(db)
    return templates.TemplateResponse(
        request,
        "tasks/form.html",
        {
            "request": request,
            "task": None,
            "projects": projects,
            "users": users,
            "departments": TASK_DEPARTMENTS,
            "statuses": TASK_STATUSES,
            "status_labels": TASK_STATUS_LABELS,
            "priorities": TASK_PRIORITIES,
            "priority_labels": TASK_PRIORITY_LABELS,
        },
    )


@router.post("/new")
def tasks_create(
    request: Request,
    title: str = Form(...),
    department: str = Form(""),
    status: str = Form("todo"),
    priority: str = Form("medium"),
    due_date: str = Form(""),
    assigned_to: List[str] = Form(default=[]),
    project_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    parsed_date = None
    if due_date.strip():
        try:
            parsed_date = date.fromisoformat(due_date.strip())
        except ValueError:
            pass

    pid = None
    if project_id.strip():
        try:
            pid = int(project_id.strip())
        except ValueError:
            pass

    if status not in TASK_STATUSES:
        status = "todo"
    if priority not in TASK_PRIORITIES:
        priority = "medium"

    task = Task(
        title=title.strip(),
        department=department.strip() or None,
        status=status,
        priority=priority,
        due_date=parsed_date,
        assigned_to=_assigned_names(assigned_to),
        project_id=pid,
        notes=notes.strip() or None,
        is_completed=(status == "done"),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_activity(
        db,
        request.session.get("user_name"),
        "Created task",
        entity_type="task",
        entity_id=task.id,
        detail=task.title,
    )
    return RedirectResponse(url=f"/tasks/{task.id}", status_code=303)


@router.get("/{task_id}", response_class=HTMLResponse)
def tasks_detail(
    request: Request,
    task_id: int,
    success: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .options(
            joinedload(Task.project),
            joinedload(Task.thread),
            joinedload(Task.subtasks),
            joinedload(Task.files),
        )
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        return RedirectResponse(url="/tasks?error=Task+not+found", status_code=303)

    # Non-admins can only view tasks they're assigned to
    if not _is_admin(request):
        user_name = request.session.get("user_name", "")
        assigned = task.assigned_to or ""
        names = [n.strip() for n in assigned.split(",")]
        if user_name not in names:
            return RedirectResponse(url="/tasks", status_code=303)

    users = _get_users(db)

    return templates.TemplateResponse(
        request,
        "tasks/detail.html",
        {
            "request": request,
            "task": task,
            "users": users,
            "status_labels": TASK_STATUS_LABELS,
            "priority_labels": TASK_PRIORITY_LABELS,
            "statuses": TASK_STATUSES,
            "note_types": NOTE_TYPES,
            "note_type_labels": NOTE_TYPE_LABELS,
            "success": success or None,
            "error": error or None,
            "today": date.today(),
        },
    )


@router.get("/{task_id}/edit", response_class=HTMLResponse)
def tasks_edit_form(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)
    projects = db.query(Project).order_by(Project.name).all()
    users = _get_users(db)
    return templates.TemplateResponse(
        request,
        "tasks/form.html",
        {
            "request": request,
            "task": task,
            "projects": projects,
            "users": users,
            "departments": TASK_DEPARTMENTS,
            "statuses": TASK_STATUSES,
            "status_labels": TASK_STATUS_LABELS,
            "priorities": TASK_PRIORITIES,
            "priority_labels": TASK_PRIORITY_LABELS,
        },
    )


@router.post("/{task_id}/edit")
def tasks_update(
    request: Request,
    task_id: int,
    title: str = Form(...),
    department: str = Form(""),
    status: str = Form("todo"),
    priority: str = Form("medium"),
    due_date: str = Form(""),
    assigned_to: List[str] = Form(default=[]),
    project_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)

    parsed_date = None
    if due_date.strip():
        try:
            parsed_date = date.fromisoformat(due_date.strip())
        except ValueError:
            pass

    pid = None
    if project_id.strip():
        try:
            pid = int(project_id.strip())
        except ValueError:
            pass

    task.title = title.strip()
    task.department = department.strip() or None
    task.status = status if status in TASK_STATUSES else task.status
    task.priority = priority if priority in TASK_PRIORITIES else task.priority
    task.due_date = parsed_date
    task.assigned_to = _assigned_names(assigned_to)
    task.project_id = pid
    task.notes = notes.strip() or None
    task.is_completed = task.status == "done"

    db.commit()
    log_activity(
        db,
        request.session.get("user_name"),
        "Updated task",
        entity_type="task",
        entity_id=task.id,
        detail=task.title,
    )
    return RedirectResponse(url=f"/tasks/{task_id}?success=Task+updated", status_code=303)


@router.post("/{task_id}/status")
def tasks_set_status(
    request: Request,
    task_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task and status in TASK_STATUSES:
        task.status = status
        task.is_completed = status == "done"
        db.commit()
        log_activity(
            db,
            request.session.get("user_name"),
            f"Set task status to {TASK_STATUS_LABELS.get(status, status)}",
            entity_type="task",
            entity_id=task_id,
            detail=task.title,
        )
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/note")
def tasks_add_note(
    request: Request,
    task_id: int,
    body: str = Form(...),
    note_type: str = Form("comment"),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)
    if not body.strip():
        return RedirectResponse(
            url=f"/tasks/{task_id}?error=Note+body+cannot+be+empty", status_code=303
        )
    if note_type not in NOTE_TYPES:
        note_type = "comment"

    note = TaskNote(
        task_id=task_id,
        author=request.session.get("user_name") or "Unknown",
        body=body.strip(),
        note_type=note_type,
    )
    db.add(note)

    # Auto-transition status based on note type
    if note_type == "revision_request" and task.status == "review":
        task.status = "in_progress"
        task.is_completed = False
    elif note_type == "approval":
        task.status = "done"
        task.is_completed = True

    db.commit()
    log_activity(
        db,
        request.session.get("user_name"),
        f"Added {NOTE_TYPE_LABELS.get(note_type, note_type)} to task",
        entity_type="task",
        entity_id=task_id,
        detail=task.title,
    )
    return RedirectResponse(url=f"/tasks/{task_id}#notes", status_code=303)


@router.post("/{task_id}/note/{note_id}/delete")
def tasks_delete_note(
    request: Request,
    task_id: int,
    note_id: int,
    db: Session = Depends(get_db),
):
    note = (
        db.query(TaskNote)
        .filter(TaskNote.id == note_id, TaskNote.task_id == task_id)
        .first()
    )
    if note:
        db.delete(note)
        db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#notes", status_code=303)


@router.post("/{task_id}/delete")
def tasks_delete(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        # Delete stored files from storage
        for f in task.files:
            try:
                storage.delete(f.stored_path)
            except Exception:
                pass
        title = task.title
        db.delete(task)
        db.commit()
        log_activity(
            db,
            request.session.get("user_name"),
            "Deleted task",
            entity_type="task",
            detail=title,
        )
    return RedirectResponse(url="/tasks", status_code=303)


# ── Sub-tasks ─────────────────────────────────────────────────────────────────

@router.post("/{task_id}/subtasks/new")
def subtask_create(
    request: Request,
    task_id: int,
    title: str = Form(...),
    assigned_to: List[str] = Form(default=[]),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)

    parsed_date = None
    if due_date.strip():
        try:
            parsed_date = date.fromisoformat(due_date.strip())
        except ValueError:
            pass

    subtask = SubTask(
        task_id=task_id,
        title=title.strip(),
        assigned_to=_assigned_names(assigned_to),
        due_date=parsed_date,
    )
    db.add(subtask)
    db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#subtasks", status_code=303)


@router.post("/{task_id}/subtasks/{subtask_id}/toggle")
def subtask_toggle(
    request: Request,
    task_id: int,
    subtask_id: int,
    db: Session = Depends(get_db),
):
    subtask = (
        db.query(SubTask)
        .filter(SubTask.id == subtask_id, SubTask.task_id == task_id)
        .first()
    )
    if subtask:
        subtask.is_completed = not subtask.is_completed
        db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#subtasks", status_code=303)


@router.post("/{task_id}/subtasks/{subtask_id}/delete")
def subtask_delete(
    request: Request,
    task_id: int,
    subtask_id: int,
    db: Session = Depends(get_db),
):
    subtask = (
        db.query(SubTask)
        .filter(SubTask.id == subtask_id, SubTask.task_id == task_id)
        .first()
    )
    if subtask:
        # Delete subtask files from storage (DB CASCADE will remove the rows)
        subtask_files = db.query(TaskFile).filter(TaskFile.subtask_id == subtask_id).all()
        for f in subtask_files:
            try:
                storage.delete(f.stored_path)
            except Exception:
                pass
        db.delete(subtask)
        db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#subtasks", status_code=303)


# ── File uploads ──────────────────────────────────────────────────────────────

@router.post("/{task_id}/files/upload")
def task_file_upload(
    request: Request,
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return RedirectResponse(url="/tasks", status_code=303)

    if not file.filename:
        return RedirectResponse(url=f"/tasks/{task_id}?error=No+file+selected#files", status_code=303)

    try:
        stored_path, original_filename, size_bytes = _save_task_file(file, task_id)
    except ValueError as e:
        return RedirectResponse(url=f"/tasks/{task_id}?error={str(e).replace(' ', '+')}#files", status_code=303)

    tf = TaskFile(
        task_id=task_id,
        subtask_id=None,
        original_filename=original_filename,
        stored_path=stored_path,
        size_bytes=size_bytes,
        uploaded_by=request.session.get("user_name") or "Unknown",
    )
    db.add(tf)
    db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#files", status_code=303)


@router.post("/{task_id}/files/{file_id}/delete")
def task_file_delete(
    request: Request,
    task_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    tf = db.query(TaskFile).filter(TaskFile.id == file_id, TaskFile.task_id == task_id).first()
    if tf:
        try:
            storage.delete(tf.stored_path)
        except Exception:
            pass
        db.delete(tf)
        db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#files", status_code=303)


@router.post("/{task_id}/subtasks/{subtask_id}/files/upload")
def subtask_file_upload(
    request: Request,
    task_id: int,
    subtask_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    subtask = (
        db.query(SubTask)
        .filter(SubTask.id == subtask_id, SubTask.task_id == task_id)
        .first()
    )
    if not subtask:
        return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)

    if not file.filename:
        return RedirectResponse(url=f"/tasks/{task_id}?error=No+file+selected#subtasks", status_code=303)

    try:
        stored_path, original_filename, size_bytes = _save_task_file(file, task_id)
    except ValueError as e:
        return RedirectResponse(url=f"/tasks/{task_id}?error={str(e).replace(' ', '+')}#subtasks", status_code=303)

    tf = TaskFile(
        task_id=task_id,
        subtask_id=subtask_id,
        original_filename=original_filename,
        stored_path=stored_path,
        size_bytes=size_bytes,
        uploaded_by=request.session.get("user_name") or "Unknown",
    )
    db.add(tf)
    db.commit()
    return RedirectResponse(url=f"/tasks/{task_id}#subtasks", status_code=303)
