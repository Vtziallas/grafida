def test_search_finds_evidence_and_isolates_users(auth_client, client):
    import io

    from docx import Document as Docx
    b = io.BytesIO(); d = Docx()
    d.add_paragraph("μίσθωση ακινήτου στην Καλλιθέα με μηνιαίο μίσθωμα")
    d.save(b)
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Μίσθωση"}).json()["id"]
    auth_client.post(f"/api/cases/{case_id}/evidence",
        files={"file": ("m.docx", b.getvalue(), "application/x")},
        data={"description": "Μισθωτήριο"})
    r = auth_client.get("/api/search?q=μίσθωμα")
    assert r.status_code == 200 and len(r.json()) >= 1
    assert r.json()[0]["kind"] == "evidence"
    # user isolation
    client.post("/api/auth/register", json={"email": "z@z.gr", "password": "secret123"})
    client.post("/api/auth/login", json={"email": "z@z.gr", "password": "secret123"})
    assert client.get("/api/search?q=μίσθωμα").json() == []


def test_dashboard(auth_client):
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    from datetime import date, timedelta
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Κατάθεση", "due_date": str(date.today() + timedelta(days=3))})
    d = auth_client.get("/api/dashboard").json()
    assert len(d["open_cases"]) == 1 and len(d["deadlines"]) == 1
