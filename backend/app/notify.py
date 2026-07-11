"""Deadline email alerts: thresholds 7/3/1 days before due and 0 for overdue.

Each threshold fires once per deadline (tracked in Deadline.alerts_sent).
Recipient: settings.notify_email, else the owning user's email.
"""
import smtplib
from datetime import date
from email.mime.text import MIMEText

from app.config import settings
from app.db import SessionLocal
from app.models import Case, Deadline, User

THRESHOLDS = (7, 3, 1, 0)


def smtp_send(to: str, subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user or "grafida@localhost"
    msg["To"] = to
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
        s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.sendmail(msg["From"], [to], msg.as_string())


def run_deadline_alerts(db, sender=smtp_send, today: date | None = None) -> int:
    """Send at most one email per deadline per run; returns emails sent."""
    today = today or date.today()
    sent = 0
    rows = (db.query(Deadline)
            .filter(Deadline.completed_at.is_(None)).all())
    for d in rows:
        days_left = (d.due_date - today).days
        due_now = [t for t in THRESHOLDS
                   if days_left <= t and t not in (d.alerts_sent or [])]
        if not due_now or days_left < 0 and 0 in (d.alerts_sent or []):
            continue
        case = db.get(Case, d.case_id)
        user = db.get(User, d.owner_user_id)
        to = settings.notify_email or (user.email if user else "")
        if not to:
            continue
        when = ("ΕΚΠΡΟΘΕΣΜΗ" if days_left < 0 else "σήμερα" if days_left == 0
                else f"σε {days_left} ημέρες")
        subject = f"Grafida — Προθεσμία {when}: {d.title}"
        body = (f"Υπόθεση: {case.title if case else ''}\n"
                f"Προθεσμία: {d.title}\nΗμερομηνία: {d.due_date}\n\n"
                "Η προθεσμία έχει καταχωριστεί και επιβεβαιωθεί από εσάς. "
                "Το Grafida υπενθυμίζει — ο δικηγόρος αποφασίζει.")
        try:
            sender(to, subject, body)
        except Exception:  # noqa: BLE001 — one bad send must not block the rest
            continue
        d.alerts_sent = sorted(set((d.alerts_sent or []) + due_now))
        sent += 1
    db.commit()
    return sent


def alerts_configured() -> bool:
    return bool(settings.smtp_host)


def run_once() -> int:
    if not alerts_configured():
        return 0
    db = SessionLocal()
    try:
        return run_deadline_alerts(db)
    finally:
        db.close()
