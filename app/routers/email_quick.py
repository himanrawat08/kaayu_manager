import asyncio
import html
import logging

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.project import Project
from app.services.email_sender import send_quick_email

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_send(to_email: str, to_name: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Run async send in a new event loop (called from sync route)."""
    return asyncio.run(send_quick_email(to_email, to_name, subject, html_body))


def _body_to_html(body: str) -> str:
    """Safely convert plain-text email body to HTML (escape first, then convert newlines)."""
    return html.escape(body).replace("\n", "<br>")


@router.post("/contacts/{client_id}/send-email")
def client_send_email(
    client_id: int,
    subject: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.email:
        return RedirectResponse(url=f"/contacts/{client_id}?error_msg=No+email+address", status_code=303)

    ok, err = _run_send(client.email, client.name, subject, _body_to_html(body))

    if ok:
        return RedirectResponse(url=f"/contacts/{client_id}?sent=1", status_code=303)
    else:
        logger.error("Email send failed for client %s: %s", client_id, err)
        return RedirectResponse(
            url=f"/contacts/{client_id}?error_msg=Failed+to+send+email.+Please+check+SMTP+settings.",
            status_code=303,
        )


@router.post("/projects/{project_id}/send-email")
def project_send_email(
    project_id: int,
    subject: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.client.email:
        return RedirectResponse(
            url=f"/projects/{project_id}?error_msg=Contact+has+no+email+address", status_code=303
        )

    ok, err = _run_send(project.client.email, project.client.name, subject, _body_to_html(body))

    if ok:
        return RedirectResponse(url=f"/projects/{project_id}?sent=1", status_code=303)
    else:
        logger.error("Email send failed for project %s: %s", project_id, err)
        return RedirectResponse(
            url=f"/projects/{project_id}?error_msg=Failed+to+send+email.+Please+check+SMTP+settings.",
            status_code=303,
        )
