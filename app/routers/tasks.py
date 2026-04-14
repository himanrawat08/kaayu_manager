from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import nulls_last
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
    Task,
    TaskNote,
)
from app.services.log_activity import log_activity
from app.templates_config import templates

router = APIRouter(prefix="/tasks")


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

    tasks = query.order_by(nulls_last(Task.due_date.asc()), Task.created_at.desc()).all()

    # Summary counts (unfiltered)
    all_tasks = db.query(Task.status).all()
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
    return templates.TemplateResponse(
        request,
        "tasks/form.html",
        {
            "request": request,
            "task": None,
            "projects": projects,
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
    assigned_to: str = Form(""),
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
        assigned_to=assigned_to.strip() or None,
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
        .options(joinedload(Task.project), joinedload(Task.thread))
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        return RedirectResponse(url="/tasks?error=Task+not+found", status_code=303)

    return templates.TemplateResponse(
        request,
        "tasks/detail.html",
        {
            "request": request,
            "task": task,
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
    return templates.TemplateResponse(
        request,
        "tasks/form.html",
        {
            "request": request,
            "task": task,
            "projects": projects,
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
    assigned_to: str = Form(""),
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
    task.assigned_to = assigned_to.strip() or None
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
