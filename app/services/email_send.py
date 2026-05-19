"""发送邮件（忘记密码验证码等）；支持 SMTP 与 Mock。"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def send_email_sync(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if settings.email_use_mock:
        logger.info("email mock to=%s subject=%s body=%s", to, subject, body.replace("\n", " "))
        return

    host = (settings.smtp_host or "").strip()
    port = int(settings.smtp_port)
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""
    from_addr = (settings.smtp_from or user or "").strip()
    if not host or not from_addr:
        raise EmailSendError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(body, subtype="plain", charset="utf-8")

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except OSError as exc:
        logger.exception("SMTP send failed to=%s", to)
        raise EmailSendError("邮件发送失败") from exc
