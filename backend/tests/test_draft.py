import io
import time

from docx import Document as Docx


def _docx(text):
    b = io.BytesIO(); d = Docx(); d.add_paragraph(text); d.save(b)
    return b.getvalue()


def _setup(ac):
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal()
    t = DocumentType(name_gr="Ανακοπή Δ", checklist_template=["Ελέγξτε προθεσμία."])
    db.add(t); db.commit(); tid = t.id; db.close()
    for txt in ["ΕΝΩΠΙΟΝ Επειδή α", "ΕΝΩΠΙΟΝ Επειδή β", "ΕΝΩΠΙΟΝ Επειδή γ"]:
        ac.post("/api/style/samples",
                files={"file": ("s.docx", _docx(txt), "application/x")},
                data={"document_type_id": str(tid)})
    ac.post(f"/api/style/profiles/{tid}/rebuild")
    cid = ac.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = ac.post("/api/cases", json={"client_id": cid, "title": "Υ"}).json()["id"]
    ac.patch(f"/api/cases/{case_id}", json={
        "facts_text": "Ο Ιωάννης Παπαδόπουλος οφείλει 14.500,00 από 1/6/2026 "
                      "βάσει διαταγής πληρωμής"})
    ac.post(f"/api/cases/{case_id}/extract")
    for f in ac.get(f"/api/cases/{case_id}").json()["facts"]:
        ac.patch(f"/api/facts/{f['id']}", json={"confirmed_by_lawyer": True})
    for p in ac.get(f"/api/cases/{case_id}").json()["parties"]:
        ac.patch(f"/api/parties/{p['id']}", json={"confirmed_by_lawyer": True})
    return tid, case_id


def test_generate_document_flow(auth_client):
    tid, case_id = _setup(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/documents",
                         json={"type_id": tid, "title": "Ανακοπή 1"})
    assert r.status_code == 200
    doc_id = r.json()["id"]
    for _ in range(20):  # TestClient runs background tasks synchronously post-response
        d = auth_client.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    assert d["draft"]["status"] == "ok"
    assert "ΑΝΑΚΟΠΗ" in d["content"]
    assert d["draft"]["uncertainty_report"]["unverified_refs"] >= 1
    assert d["draft"]["inputs_manifest"]["prompt_version"] == 1


def test_requires_profile(auth_client):
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal(); t = DocumentType(name_gr="Χωρίς προφίλ", checklist_template=[])
    db.add(t); db.commit(); tid = t.id; db.close()
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    r = auth_client.post(f"/api/cases/{case_id}/documents",
                         json={"type_id": tid, "title": "Χ"})
    assert r.status_code == 400
