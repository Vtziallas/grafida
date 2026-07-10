import io

from docx import Document as Docx


def _docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    d = Docx(); d.add_paragraph(text); d.save(buf)
    return buf.getvalue()


def _case(ac):
    cid = ac.post("/api/clients", json={"name": "Π"}).json()["id"]
    return ac.post("/api/cases", json={"client_id": cid, "title": "Υ"}).json()["id"]


def test_evidence_upload_extracts_text(auth_client):
    case_id = _case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("a.docx", _docx_bytes("Μίσθωμα 1.500,00 ευρώ"),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"description": "Μισθωτήριο"})
    assert r.status_code == 200
    ev = auth_client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev[0]["exhibit_number"] == 1 and ev[0]["ocr_pending"] is False


def test_style_sample_upload(auth_client):
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal(); db.add(DocumentType(name_gr="Ανακοπή", checklist_template=[]))
    db.commit(); tid = db.query(DocumentType).first().id; db.close()
    r = auth_client.post("/api/style/samples",
        files={"file": ("s.docx", _docx_bytes("ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ..."), "application/x")},
        data={"document_type_id": str(tid)})
    assert r.status_code == 200
    samples = auth_client.get(f"/api/style/samples?document_type_id={tid}").json()
    assert len(samples) == 1 and samples[0]["status"] == "ok"


def test_bad_extension_rejected(auth_client):
    case_id = _case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("x.exe", b"MZ", "application/x")}, data={"description": ""})
    assert r.status_code == 400
