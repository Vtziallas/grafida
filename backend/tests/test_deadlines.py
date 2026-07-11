from datetime import date, timedelta


def _case(ac):
    cid = ac.post("/api/clients", json={"name": "Π", "id_number": "ΑΒ123456",
                                        "email": "p@p.gr", "phone": "6900000000",
                                        "notes": "σημείωση"}).json()["id"]
    return cid, ac.post("/api/cases", json={"client_id": cid, "title": "Υ"}).json()["id"]


def test_client_extra_fields_roundtrip(auth_client):
    cid, _ = _case(auth_client)
    d = auth_client.get(f"/api/clients/{cid}").json()
    assert d["id_number"] == "ΑΒ123456" and d["notes"] == "σημείωση"


def test_all_deadlines_listing_and_complete(auth_client):
    _, case_id = _case(auth_client)
    today = date.today()
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Κατάθεση", "due_date": str(today + timedelta(days=2))})
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Έφεση", "due_date": str(today + timedelta(days=40))})
    rows = auth_client.get("/api/deadlines").json()
    assert len(rows) == 2 and rows[0]["title"] == "Κατάθεση"
    assert rows[0]["days_left"] == 2 and rows[0]["case_title"] == "Υ"
    did = rows[0]["id"]
    auth_client.post(f"/api/deadlines/{did}/complete")
    rows = auth_client.get("/api/deadlines").json()
    assert [r for r in rows if r["id"] == did][0]["completed"] is True


def test_alert_selection_and_no_duplicates(auth_client):
    from app.db import SessionLocal
    from app.notify import run_deadline_alerts
    _, case_id = _case(auth_client)
    today = date.today()
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Σε 2 μέρες", "due_date": str(today + timedelta(days=2))})
    auth_client.post(f"/api/cases/{case_id}/deadlines",
        json={"title": "Σε 30 μέρες", "due_date": str(today + timedelta(days=30))})
    sent: list[tuple[str, str, str]] = []
    db = SessionLocal()
    n = run_deadline_alerts(db, sender=lambda to, subj, body: sent.append((to, subj, body)))
    assert n == 1 and len(sent) == 1
    assert "Σε 2 μέρες" in sent[0][1] or "Σε 2 μέρες" in sent[0][2]
    # second run: nothing new
    n = run_deadline_alerts(db, sender=lambda to, subj, body: sent.append((to, subj, body)))
    assert n == 0 and len(sent) == 1
    db.close()
