from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.style_analyze import build_profile
from app.ai.factory import get_provider
from app.auth.deps import get_current_user
from app.db import get_db
from app.models import StyleProfile, StyleSample, User

router = APIRouter(prefix="/api/style/profiles")


def _serialize(p: StyleProfile) -> dict:
    return {"id": p.id, "document_type_id": p.document_type_id,
            "version": p.version, "spec": p.spec,
            "approved_by_lawyer": p.approved_by_lawyer,
            "built_from_sample_ids": p.built_from_sample_ids}


@router.get("/{document_type_id}")
def get_profile(document_type_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    p = (db.query(StyleProfile)
         .filter_by(owner_user_id=user.id, document_type_id=document_type_id)
         .order_by(StyleProfile.version.desc()).first())
    if not p:
        raise HTTPException(404, "Δεν υπάρχει προφίλ ύφους")
    return _serialize(p)


@router.post("/{document_type_id}/rebuild")
def rebuild(document_type_id: int, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    samples = (db.query(StyleSample)
               .filter_by(owner_user_id=user.id,
                          document_type_id=document_type_id, status="ok").all())
    if len(samples) < 3:
        raise HTTPException(400,
            f"Χρειάζονται τουλάχιστον 3 δείγματα ({len(samples)}/3). "
            "Συνιστώνται 10 για καλύτερη ποιότητα.")
    spec = build_profile(get_provider(), [s.scrubbed_text for s in samples])
    prev = (db.query(StyleProfile)
            .filter_by(owner_user_id=user.id, document_type_id=document_type_id)
            .order_by(StyleProfile.version.desc()).first())
    p = StyleProfile(owner_user_id=user.id, document_type_id=document_type_id,
                     version=(prev.version + 1) if prev else 1, spec=spec,
                     built_from_sample_ids=[s.id for s in samples])
    db.add(p); db.commit()
    return _serialize(p)


class SpecPatch(BaseModel):
    spec: dict


@router.patch("/{profile_id}")
def patch(profile_id: int, body: SpecPatch,
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(StyleProfile).filter_by(id=profile_id, owner_user_id=user.id).first()
    if not p:
        raise HTTPException(404)
    p.spec = body.spec; p.approved_by_lawyer = True
    db.commit()
    return _serialize(p)
