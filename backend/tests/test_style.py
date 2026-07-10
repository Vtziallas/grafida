import io

from docx import Document as Docx


def _docx(text):
    b = io.BytesIO(); d = Docx(); d.add_paragraph(text); d.save(b)
    return b.getvalue()


def _type_id():
    from app.db import SessionLocal
    from app.models import DocumentType
    db = SessionLocal()
    t = DocumentType(name_gr="Ανακοπή Τ", checklist_template=[])
    db.add(t); db.commit(); tid = t.id; db.close()
    return tid


def _upload(ac, tid, text):
    ac.post("/api/style/samples",
            files={"file": ("s.docx", _docx(text), "application/x")},
            data={"document_type_id": str(tid)})


def test_rebuild_requires_three_samples(auth_client):
    tid = _type_id()
    _upload(auth_client, tid, "ΕΝΩΠΙΟΝ ΤΟΥ ΔΙΚΑΣΤΗΡΙΟΥ Επειδή α")
    r = auth_client.post(f"/api/style/profiles/{tid}/rebuild")
    assert r.status_code == 400 and "1/3" in r.json()["detail"]


def test_rebuild_builds_profile(auth_client):
    tid = _type_id()
    for t in ["ΕΝΩΠΙΟΝ ΤΟΥ Επειδή πρώτον", "ΕΝΩΠΙΟΝ ΤΟΥ Επειδή δεύτερον",
              "ΕΝΩΠΙΟΝ ΤΟΥ Επειδή τρίτον"]:
        _upload(auth_client, tid, t)
    r = auth_client.post(f"/api/style/profiles/{tid}/rebuild")
    assert r.status_code == 200
    spec = r.json()["spec"]
    assert "Επειδή" in spec["phrase_bank"]["transitions"]
    r2 = auth_client.get(f"/api/style/profiles/{tid}")
    assert r2.json()["version"] == 1
