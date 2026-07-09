def _mk_case(ac):
    cid = ac.post("/api/clients", json={"name": "Πελάτης"}).json()["id"]
    return ac.post("/api/cases", json={"client_id": cid, "title": "Υπόθεση 1",
                                       "category": "civil"}).json()["id"]


def test_case_crud_and_isolation(auth_client, client):
    case_id = _mk_case(auth_client)
    r = auth_client.get(f"/api/cases/{case_id}")
    assert r.status_code == 200 and r.json()["title"] == "Υπόθεση 1"
    auth_client.patch(f"/api/cases/{case_id}", json={"facts_text": "γεγονότα"})
    assert auth_client.get(f"/api/cases/{case_id}").json()["facts_text"] == "γεγονότα"
    # second user cannot see it
    client.post("/api/auth/register", json={"email": "x@x.gr", "password": "secret123"})
    client.post("/api/auth/login", json={"email": "x@x.gr", "password": "secret123"})
    assert client.get(f"/api/cases/{case_id}").status_code == 404


def test_deadline_and_fact_confirm(auth_client):
    case_id = _mk_case(auth_client)
    r = auth_client.post(f"/api/cases/{case_id}/deadlines",
                         json={"title": "Κατάθεση", "due_date": "2026-09-01"})
    assert r.status_code == 200
    d = auth_client.get(f"/api/cases/{case_id}").json()
    assert d["deadlines"][0]["title"] == "Κατάθεση"
