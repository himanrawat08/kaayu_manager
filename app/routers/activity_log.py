from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system_log import SystemLog, SYSTEM_LOG_CAP

router = APIRouter(prefix="/activity-log")
templates = Jinja2Templates(directory="app/templates")

PAGE_SIZE = 50


@router.get("", response_class=HTMLResponse)
def activity_log(
    request: Request,
    page: int = 1,
    user: str = "",
    entity: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(SystemLog)

    if user.strip():
        query = query.filter(SystemLog.user_name.ilike(f"%{user.strip()}%"))
    if entity.strip():
        query = query.filter(SystemLog.entity_type == entity.strip())

    total = query.count()
    logs = (
        query
        .order_by(SystemLog.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    # Distinct entity types for filter dropdown
    entity_types = [
        r[0] for r in
        db.query(SystemLog.entity_type).distinct().filter(SystemLog.entity_type.isnot(None)).all()
    ]

    return templates.TemplateResponse(
        "activity_log.html",
        {
            "request": request,
            "logs": logs,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "page_size": PAGE_SIZE,
            "filter_user": user,
            "filter_entity": entity,
            "entity_types": sorted(entity_types),
            "log_cap": SYSTEM_LOG_CAP,
        },
    )
