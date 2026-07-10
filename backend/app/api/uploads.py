from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile)
from sqlalchemy.orm import Session

from app.api.cases import get_case
from app.audit import audit
from app.auth.deps import get_current_user
from app.db import get_db
from app.files.extract import extract_text
from app.files.storage import save_upload
from app.models import DocumentType, Evidence, StyleSample, User

router = APIRouter(prefix="/api")
ALLOWED = (".pdf", ".docx", ".txt")
MAX_BYTES = 15 * 1024 * 1024


async def _read(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(ALLOWED):
        raise HTTPException(400, "Επιτρέπονται μόνο αρχεία PDF, DOCX, TXT")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Το αρχείο ξεπερνά τα 15MB")
    return data


@router.post("/cases/{case_id}/evidence")
async def upload_evidence(case_id: int, file: UploadFile = File(...),
                          description: str = Form(""),
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    get_case(db, user, case_id)
    data = await _read(file)
    path = save_upload(data, file.filename, f"u{user.id}/evidence")
    text, pending = extract_text(path)
    n = (db.query(Evidence).filter_by(case_id=case_id).count()) + 1
    e = Evidence(owner_user_id=user.id, case_id=case_id, exhibit_number=n,
                 description=description or file.filename, file_path=path,
                 extracted_text=text, ocr_pending=pending)
    db.add(e); db.flush()
    audit(db, user.id, "upload.evidence", "evidence", e.id); db.commit()
    return {"id": e.id, "exhibit_number": n, "ocr_pending": pending}


@router.post("/style/samples")
async def upload_sample(file: UploadFile = File(...),
                        document_type_id: int = Form(...),
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not db.get(DocumentType, document_type_id):
        raise HTTPException(404, "Άγνωστος τύπος εγγράφου")
    data = await _read(file)
    path = save_upload(data, file.filename, f"u{user.id}/samples")
    text, pending = extract_text(path)
    s = StyleSample(owner_user_id=user.id, document_type_id=document_type_id,
                    file_path=path, original_text=text, scrubbed_text="",
                    status="ocr_pending" if pending else "ok")
    db.add(s); db.flush()
    audit(db, user.id, "upload.sample", "style_sample", s.id); db.commit()
    return {"id": s.id, "status": s.status}


@router.get("/style/samples")
def list_samples(document_type_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    rows = db.query(StyleSample).filter_by(
        owner_user_id=user.id, document_type_id=document_type_id).all()
    return [{"id": s.id, "status": s.status,
             "chars": len(s.original_text)} for s in rows]


@router.delete("/style/samples/{sample_id}")
def delete_sample(sample_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    s = db.query(StyleSample).filter_by(id=sample_id, owner_user_id=user.id).first()
    if not s:
        raise HTTPException(404)
    db.delete(s); db.commit()
    return {"ok": True}
