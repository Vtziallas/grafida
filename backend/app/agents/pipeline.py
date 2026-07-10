import hashlib
import json

from app.agents.checklist import run_checks
from app.agents.draft_agent import (build_case_file, leak_scan, overlap_scan,
                                    run_draft)
from app.ai.factory import get_provider
from app.config import settings
from app.db import SessionLocal
from app.models import (AIDraft, Case, Document, DocumentType, DocumentVersion,
                        StyleProfile, StyleSample)
from app.search.index import index_text


def generate_document(document_id: int):
    db = SessionLocal()
    draft_row = (db.query(AIDraft).filter_by(document_id=document_id)
                 .order_by(AIDraft.id.desc()).first())
    try:
        doc = db.get(Document, document_id)
        case = db.get(Case, doc.case_id)
        dtype = db.get(DocumentType, doc.type_id)
        profile = (db.query(StyleProfile)
                   .filter_by(owner_user_id=doc.owner_user_id,
                              document_type_id=doc.type_id)
                   .order_by(StyleProfile.version.desc()).first())
        provider = get_provider()
        case_file = build_case_file(db, case)
        qvec = provider.embed([json.dumps(case_file, ensure_ascii=False)[:2000]])[0]
        samples = (db.query(StyleSample)
                   .filter_by(owner_user_id=doc.owner_user_id,
                              document_type_id=doc.type_id, status="ok")
                   .filter(StyleSample.embedding.isnot(None))
                   .order_by(StyleSample.embedding.cosine_distance(qvec))
                   .limit(3).all())
        exemplars = [s.scrubbed_text for s in samples]
        content, report = run_draft(provider, case_file, profile.spec,
                                    exemplars, dtype.name_gr)
        ver = DocumentVersion(owner_user_id=doc.owner_user_id, document_id=doc.id,
                              version_no=1, content=content, author="ai",
                              content_hash=hashlib.sha256(content.encode()).hexdigest())
        db.add(ver); db.flush()
        doc.current_version_id = ver.id
        draft_row.document_version_id = ver.id
        draft_row.style_profile_id = profile.id
        draft_row.status = "ok"
        draft_row.uncertainty_report = report
        draft_row.inputs_manifest = {
            "model": settings.ai_chat_model if settings.ai_provider != "mock" else "mock",
            "prompt_version": report["prompt_version"],
            "profile_id": profile.id, "profile_version": profile.version,
            "sample_ids": [s.id for s in samples],
            "case_file_hash": hashlib.sha256(
                json.dumps(case_file, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
        }
        findings = leak_scan(content, case_file) + overlap_scan(content, exemplars)
        run_checks(db, doc, case_file, content, dtype, extra_findings=findings)
        index_text(db, doc.owner_user_id, "document", doc.id, case.id,
                   content, provider)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        if draft_row:
            draft_row.status = "failed"
            draft_row.error = f"Η δημιουργία απέτυχε: {e}"
            db.commit()
    finally:
        db.close()
