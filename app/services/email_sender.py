from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings


async def send_quick_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    from_name: str | None = None,
    from_email: str | None = None,
) -> tuple[bool, str]:
    """Send a single quick email. Returns (success, error_message)."""
    _from_name = from_name or settings.FROM_NAME
    _from_email = from_email or settings.FROM_EMAIL

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{_from_name} <{_from_email}>"
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_TLS,
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)
