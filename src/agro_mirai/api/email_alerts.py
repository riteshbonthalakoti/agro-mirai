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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def send_alert_email(subject: str, body: str, html_body: str | None = None) -> bool:
    """Returns True if the email was actually sent. Never raises --
    missing config or an SMTP failure both just log and return False,
    same never-raise contract as every other external-API client here.
    ``body`` is always sent as the plain-text part (some clients/spam
    filters prefer it present); ``html_body``, if given, rides alongside
    it as the part most clients actually render."""
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    to_addr = os.environ.get("ALERT_EMAIL_TO", "").strip()
    if not (user and password and to_addr):
        logger.warning("email_alerts: SMTP_USER/SMTP_PASS/ALERT_EMAIL_TO not fully configured, skipping")
        return False

    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
    else:
        msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = f"AGRO MIRAI Alerts <{user}>"
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=15) as server:
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001 -- an alert failing to send must never raise
        logger.warning("email_alerts: send failed: %s", exc)
        return False


# Brand colors, matching mobile/src/theme.ts's C constant -- keep these two
# in sync by hand if the app's palette ever changes.
_GREEN = "#2E7D32"
_RED = "#B3261E"
_AMBER = "#B8860B"
_TEXT = "#1A1D19"
_MUTED = "#666D64"
_BORDER = "#DDE1D9"
_SURFACE = "#F5F6F3"


def render_alert_html(
    *,
    heading: str,
    severity: str,
    intro: str,
    rows: list[dict],
    footnote: str,
) -> str:
    """One shared HTML template for every alert email this project sends
    (currently just the quota alert, but kept generic). ``severity`` is
    "critical" or "warning", driving the accent color. ``rows`` is a list
    of {"label": str, "value": str} pairs rendered as a simple two-column
    table -- the per-key breakdown for a quota alert, or whatever fits
    the next alert type that reuses this."""
    accent = _RED if severity == "critical" else _AMBER
    badge = "CRITICAL" if severity == "critical" else "WARNING"

    rows_html = "\n".join(
        f"""<tr>
          <td style="padding:10px 16px;border-bottom:1px solid {_BORDER};color:{_MUTED};font-size:13px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">{r['label']}</td>
          <td style="padding:10px 16px;border-bottom:1px solid {_BORDER};color:{_TEXT};font-size:13px;font-weight:600;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;text-align:right;">{r['value']}</td>
        </tr>"""
        for r in rows
    )

    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:{_SURFACE};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_SURFACE};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#FFFFFF;border-radius:16px;overflow:hidden;border:1px solid {_BORDER};">
          <tr>
            <td style="background-color:{_GREEN};padding:20px 28px;">
              <span style="color:#FFFFFF;font-size:18px;font-weight:800;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;letter-spacing:0.3px;">AGRO MIRAI</span>
              <span style="color:rgba(255,255,255,0.85);font-size:13px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;float:right;margin-top:3px;">System Alert</span>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px 28px;">
              <span style="display:inline-block;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:800;letter-spacing:0.6px;padding:4px 10px;border-radius:12px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">{badge}</span>
              <h1 style="margin:14px 0 6px 0;color:{_TEXT};font-size:20px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">{heading}</h1>
              <p style="margin:0 0 20px 0;color:{_MUTED};font-size:14px;line-height:1.5;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">{intro}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_SURFACE};border-radius:10px;overflow:hidden;">
                {rows_html}
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 28px 28px 28px;">
              <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">{footnote}</p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0 0;color:{_MUTED};font-size:11px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">Sent automatically by AGRO MIRAI's monitoring cron &middot; agromirai.vercel.app</p>
      </td>
    </tr>
  </table>
</body>
</html>"""
