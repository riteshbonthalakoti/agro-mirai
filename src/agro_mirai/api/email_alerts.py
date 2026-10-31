"""Email alerts for the team (Module 60) -- currently just the API
quota-near-limit warning (tools/quota_alert_sweep.py), kept generic
enough to reuse for any future "something needs a human" case.

Gmail SMTP with an app password (SMTP_USER/SMTP_PASS env vars) --
free, no new service, no API key to manage beyond the one app password
already generated at myaccount.google.com/apppasswords. Never raises:
an alert that fails to send must never crash whatever triggered it.
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def send_alert_email(subject: str, body: str) -> bool:
    """Returns True if the email was actually sent. Never raises --
    missing config or an SMTP failure both just log and return False,
    same never-raise contract as every other external-API client here."""
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    to_addr = os.environ.get("ALERT_EMAIL_TO", "").strip()
    if not (user and password and to_addr):
        logger.warning("email_alerts: SMTP_USER/SMTP_PASS/ALERT_EMAIL_TO not fully configured, skipping")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=15) as server:
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001 -- an alert failing to send must never raise
        logger.warning("email_alerts: send failed: %s", exc)
        return False
