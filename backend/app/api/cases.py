from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from rapidfuzz import fuzz as _fuzz
from sqlalchemy.orm import Session

from app.agents.intake_extract import run_extraction
from app.ai.factory import get_provider
from app.audit import audit
from app.auth.deps import get_current_user
from app.db import get_db
from app.models import (Case, CaseFact, Client, Deadline, Document,
                        DocumentType, Evidence, Party, User)

router = APIRouter(prefix="/api")


def get_case(db: Session, user: User, case_id: int) -> Case:
    c = db.query(Case).filter_by(id=case_id, owner_user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Η υπόθεση δεν βρέθηκε")
    return c


class CaseIn(BaseModel):
    client_id: int
    title: str
    category: str = "civil"
    court_name: str = ""


class CasePatch(BaseModel):
    title: str | None = None
    court_name: str | None = None
    status: str | None = None
    next_action: str | None = None
    ref_numbers: str | None = None
    facts_text: str | None = None


class DeadlineIn(BaseModel):
    title: str
    due_date: date


class PartyPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    confirmed_by_lawyer: bool | None = None


class FactPatch(BaseModel):
    value: str | None = None
    description: str | None = None
    confirmed_by_lawyer: bool | None = None


@router.get("/document-types")
def doc_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name_gr} for t in db.query(DocumentType).all()]


@router.post("/cases")
def create(body: CaseIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if not db.query(Client).filter_by(id=body.client_id, owner_user_id=user.id).first():
        raise HTTPException(404, "Ο πελάτης δεν βρέθηκε")
    c = Case(owner_user_id=user.id, **body.model_dump())
    db.add(c); db.flush()
    audit(db, user.id, "case.create", "case", c.id); db.commit()
    return {"id": c.id}


@router.get("/cases")
def list_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Case).filter_by(owner_user_id=user.id).order_by(Case.id.desc()).all()
    return [{"id": c.id, "title": c.title, "status": c.status,
             "court_name": c.court_name, "next_action": c.next_action} for c in rows]


@router.get("/cases/{case_id}")
def detail(case_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    client = db.get(Client, c.client_id)
    types = db.query(DocumentType).all()
    docs = db.query(Document).filter_by(case_id=c.id).all()
    tmap = {t.id: t.name_gr for t in types}
    return {
        "id": c.id, "title": c.title, "category": c.category, "status": c.status,
        "court_name": c.court_name, "next_action": c.next_action,
        "ref_numbers": c.ref_numbers, "facts_text": c.facts_text,
        "client": {"id": client.id, "name": client.name},
        "parties": [{"id": p.id, "name": p.name, "role": p.role,
                     "source_quote": p.source_quote, "confidence": p.confidence,
                     "confirmed": p.confirmed_by_lawyer}
                    for p in db.query(Party).filter_by(case_id=c.id)],
        "facts": [{"id": f.id, "kind": f.kind, "value": f.value,
                   "description": f.description, "source_quote": f.source_quote,
                   "confidence": f.confidence, "confirmed": f.confirmed_by_lawyer,
                   "conflict_group": f.conflict_group}
                  for f in db.query(CaseFact).filter_by(case_id=c.id)],
        "deadlines": [{"id": d.id, "title": d.title, "due_date": str(d.due_date),
                       "completed": d.completed_at is not None}
                      for d in db.query(Deadline).filter_by(case_id=c.id)
                                 .order_by(Deadline.due_date)],
        "documents": [{"id": d.id, "title": d.title, "status": d.status,
                       "type": tmap.get(d.type_id, "")} for d in docs],
        "evidence": [{"id": e.id, "exhibit_number": e.exhibit_number,
                      "description": e.description, "ocr_pending": e.ocr_pending}
                     for e in db.query(Evidence).filter_by(case_id=c.id)
                                .order_by(Evidence.exhibit_number)],
        "document_types": [{"id": t.id, "name": t.name_gr} for t in types],
    }


@router.patch("/cases/{case_id}")
def patch(case_id: int, body: CasePatch, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/deadlines")
def add_deadline(case_id: int, body: DeadlineIn,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    d = Deadline(owner_user_id=user.id, case_id=case_id, **body.model_dump())
    db.add(d); db.commit()
    return {"id": d.id}


@router.post("/cases/{case_id}/extract")
def extract(case_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    c = get_case(db, user, case_id)
    texts = [c.facts_text] + [e.extracted_text for e in
             db.query(Evidence).filter_by(case_id=c.id) if e.extracted_text]
    source = "\n\n".join(t for t in texts if t)
    if not source.strip():
        raise HTTPException(400, "Δεν υπάρχουν γεγονότα ή αποδεικτικά για εξαγωγή")
    data = run_extraction(get_provider(), source)
    db.query(Party).filter_by(case_id=c.id, confirmed_by_lawyer=False).delete()
    db.query(CaseFact).filter_by(case_id=c.id, confirmed_by_lawyer=False).delete()
    for p in data["parties"]:
        db.add(Party(owner_user_id=user.id, case_id=c.id, name=p.get("name") or "",
                     role=p.get("role", ""), source_quote=p.get("source_quote", ""),
                     confidence=p.get("confidence", 0.0)))
    kind_map = {"dates": "date", "amounts": "amount", "claims": "claim"}
    new_facts = []
    for key, kind in kind_map.items():
        for it in data[key]:
            new_facts.append(CaseFact(
                owner_user_id=user.id, case_id=c.id, kind=kind,
                value=it.get("value"), description=it.get("description", ""),
                source_quote=it.get("source_quote", ""),
                confidence=it.get("confidence", 0.0)))
    group = 1
    amounts = [f for f in new_facts if f.kind == "amount" and f.value]
    for i in range(len(amounts)):
        for j in range(i + 1, len(amounts)):
            a, b = amounts[i], amounts[j]
            if (a.value != b.value and
                    _fuzz.ratio(a.description, b.description) >= 80):
                a.conflict_group = b.conflict_group = group
                group += 1
    db.add_all(new_facts)
    audit(db, user.id, "extract.run", "case", c.id)
    db.commit()
    return detail(case_id, user, db)


@router.patch("/parties/{party_id}")
def patch_party(party_id: int, body: PartyPatch,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Party).filter_by(id=party_id, owner_user_id=user.id).first()
    if not p:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    if body.confirmed_by_lawyer:
        audit(db, user.id, "extract.confirm", "party", p.id)
    db.commit()
    return {"ok": True}


@router.patch("/facts/{fact_id}")
def patch_fact(fact_id: int, body: FactPatch,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.query(CaseFact).filter_by(id=fact_id, owner_user_id=user.id).first()
    if not f:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    if body.confirmed_by_lawyer:
        audit(db, user.id, "extract.confirm", "fact", f.id)
    db.commit()
    return {"ok": True}
