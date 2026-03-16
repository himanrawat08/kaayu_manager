from sqlalchemy.orm import Session

from app.models.system_log import SystemLog


def log_activity(
    db: Session,
    user_name: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Insert one system log entry. FIFO cap is enforced by the DB trigger."""
    db.add(SystemLog(
        user_name=user_name or "System",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    ))
    db.commit()
