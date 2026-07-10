from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.factory import get_provider
from app.auth.deps import get_current_user
from app.db import get_db
from app.models import Case, Deadline, Document, User
from app.search.service import hybrid_search

router = APIRouter(prefix="/api")


@router.get("/search")
def search(q: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if len(q.strip()) < 2:
        raise HTTPException(400, "Πολύ σύντομο ερώτημα")
    return hybrid_search(db, user.id, q.strip(), get_provider())


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = db.query(Case).filter_by(owner_user_id=user.id, status="open").all()
    cmap = {c.id: c.title for c in cases}
    horizon = date.today() + timedelta(days=14)
    dls = (db.query(Deadline)
           .filter(Deadline.owner_user_id == user.id,
                   Deadline.completed_at.is_(None),
                   Deadline.due_date <= horizon)
           .order_by(Deadline.due_date).all())
    pending = (db.query(Document)
               .filter(Document.owner_user_id == user.id,
                       Document.status == "draft").all())
    return {
        "open_cases": [{"id": c.id, "title": c.title,
                        "next_action": c.next_action} for c in cases],
        "deadlines": [{"id": d.id, "case_id": d.case_id,
                       "case_title": cmap.get(d.case_id, ""),
                       "title": d.title, "due_date": str(d.due_date)} for d in dls],
        "pending_drafts": [{"document_id": p.id, "title": p.title,
                            "status": p.status} for p in pending],
    }
