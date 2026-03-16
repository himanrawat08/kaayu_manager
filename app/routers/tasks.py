from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task, TASK_PRIORITIES
from app.services.log_activity import log_activity

router = APIRouter(prefix="/tasks")


@router.post("/new")
def create_task(
    request: Request,
    title: str = Form(...),
    due_date: str = Form(""),
    priority: str = Form("medium"),
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

    if priority not in TASK_PRIORITIES:
        priority = "medium"

    task = Task(
        title=title.strip(),
        notes=notes.strip() or None,
        due_date=parsed_date,
        priority=priority,
        project_id=pid,
    )
    db.add(task)
    db.commit()
    log_activity(db, request.session.get("user_name"), "Created task",
                 entity_type="task", entity_id=task.id, detail=task.title)
    return RedirectResponse(url="/?view=tasks", status_code=303)


@router.post("/{task_id}/toggle")
def toggle_task(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.is_completed = not task.is_completed
        db.commit()
        action = "Completed task" if task.is_completed else "Reopened task"
        log_activity(db, request.session.get("user_name"), action,
                     entity_type="task", entity_id=task_id, detail=task.title)
    return RedirectResponse(url="/?view=tasks", status_code=303)


@router.post("/{task_id}/delete")
def delete_task(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        title = task.title
        db.delete(task)
        db.commit()
        log_activity(db, request.session.get("user_name"), "Deleted task",
                     entity_type="task", detail=title)
    return RedirectResponse(url="/?view=tasks", status_code=303)
