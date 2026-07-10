import time


def _approved_doc(ac):
    from tests.test_draft import _setup
    tid, case_id = _setup(ac)
    doc_id = ac.post(f"/api/cases/{case_id}/documents",
                     json={"type_id": tid, "title": "Α"}).json()["id"]
    for _ in range(20):
        d = ac.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    return doc_id, d


def test_export_blocked_before_approval(auth_client):
    doc_id, _ = _approved_doc(auth_client)
    assert auth_client.get(f"/api/documents/{doc_id}/export").status_code == 403


def test_export_after_approval(auth_client):
    doc_id, d = _approved_doc(auth_client)
    for item in d["checklist"]:
        if item["severity"] == "red" and item["source_agent"] != "attestation":
            auth_client.post(f"/api/checklist-items/{item['id']}/override",
                             json={"note": "ok"})
    auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    r = auth_client.get(f"/api/documents/{doc_id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument")
    assert auth_client.get(f"/api/documents/{doc_id}").json()["status"] == "exported"
