"""Optional SMTP delivery. Nothing is sent (and nothing is claimed as sent) unless SMTP_* is configured."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_email(to: str, subject: str, body: str) -> bool:
    """Return True only if the SMTP server accepted the message."""
    if not smtp_configured():
        return False
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        host = os.environ["SMTP_HOST"]
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as server:
            if os.getenv("SMTP_STARTTLS", "1") != "0":
                server.starttls()
            if os.getenv("SMTP_USER"):
                server.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            server.send_message(message)
        return True
    except Exception as error:
        logger.warning("Email delivery failed (%s)", type(error).__name__)
        return False


def public_app_url() -> str:
    return os.getenv("PUBLIC_APP_URL", "http://localhost:5174").rstrip("/")


def public_api_url() -> str:
    return os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
