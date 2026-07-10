import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.pipeline import generate_document
from app.api.cases import get_case
from app.audit import audit
from app.auth.deps import get_current_user
from app.db import get_db
from app.models import (AIDraft, ChecklistItem, Document, DocumentType,
                        DocumentVersion, StyleProfile, User)

router = APIRouter(prefix="/api")


class DocIn(BaseModel):
    type_id: int
    title: str


class VersionIn(BaseModel):
    content: str


def get_doc(db, user, doc_id) -> Document:
    d = db.query(Document).filter_by(id=doc_id, owner_user_id=user.id).first()
    if not d:
        raise HTTPException(404, "Το έγγραφο δεν βρέθηκε")
    return d


@router.post("/cases/{case_id}/documents")
def create_doc(case_id: int, body: DocIn, bg: BackgroundTasks,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    if not db.get(DocumentType, body.type_id):
        raise HTTPException(404, "Άγνωστος τύπος εγγράφου")
    profile = (db.query(StyleProfile)
               .filter_by(owner_user_id=user.id, document_type_id=body.type_id)
               .first())
    if not profile:
        raise HTTPException(400,
            "Δεν υπάρχει προφίλ ύφους για αυτόν τον τύπο. Ανεβάστε δείγματα και "
            "δημιουργήστε προφίλ πρώτα.")
    doc = Document(owner_user_id=user.id, case_id=case_id,
                   type_id=body.type_id, title=body.title)
    db.add(doc); db.flush()
    db.add(AIDraft(owner_user_id=user.id, document_id=doc.id, status="running"))
    audit(db, user.id, "draft.generate", "document", doc.id)
    db.commit()
    bg.add_task(generate_document, doc.id)
    return {"id": doc.id}


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    dtype = db.get(DocumentType, d.type_id)
    draft = (db.query(AIDraft).filter_by(document_id=d.id)
             .order_by(AIDraft.id.desc()).first())
    ver = db.get(DocumentVersion, d.current_version_id) if d.current_version_id else None
    items = db.query(ChecklistItem).filter_by(document_id=d.id).all()
    return {
        "id": d.id, "title": d.title, "status": d.status, "case_id": d.case_id,
        "type": dtype.name_gr,
        "draft": {"status": draft.status if draft else "none",
                  "error": draft.error if draft else "",
                  "uncertainty_report": draft.uncertainty_report if draft else {},
                  "inputs_manifest": draft.inputs_manifest if draft else {}},
        "content": ver.content if ver else "",
        "version_no": ver.version_no if ver else 0,
        "checklist": [{"id": i.id, "severity": i.severity, "text": i.text,
                       "source_agent": i.source_agent, "status": i.status,
                       "anchor_quote": i.anchor_quote,
                       "override_note": i.override_note} for i in items],
    }


@router.post("/documents/{doc_id}/versions")
def save_version(doc_id: int, body: VersionIn,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = get_doc(db, user, doc_id)
    if d.status != "draft":
        raise HTTPException(400, "Το έγγραφο έχει ήδη εγκριθεί")
    last = (db.query(DocumentVersion).filter_by(document_id=d.id)
            .order_by(DocumentVersion.version_no.desc()).first())
    ver = DocumentVersion(owner_user_id=user.id, document_id=d.id,
                          version_no=(last.version_no + 1) if last else 1,
                          content=body.content, author="lawyer",
                          content_hash=hashlib.sha256(body.content.encode()).hexdigest())
    db.add(ver); db.flush()
    d.current_version_id = ver.id
    db.commit()
    return {"version_no": ver.version_no}
