from app.agents.consistency import check_consistency

CF = {"parties": [{"name": "Ιωάννης Παπαδόπουλος", "role": "ανακόπτων"}],
      "facts": [{"kind": "amount", "value": "14500.00", "description": "οφειλή",
                 "source_quote": "14.500,00"}],
      "evidence": [{"exhibit_number": 1, "description": "διαταγή"}]}


def test_amount_mismatch_is_red():
    findings = check_consistency(CF, "Οφειλή 15.400,00 ευρώ του Παπαδόπουλου (σχετικό 1)")
    reds = [f for f in findings if f["severity"] == "red"]
    assert any("15.400,00" in f["text"] or "14.500,00" in f["text"] for f in reds)


def test_unknown_exhibit_is_red():
    findings = check_consistency(CF, "ποσό 14.500,00 (σχετικό 7) του Παπαδόπουλου")
    assert any("σχετικό 7" in f["text"] for f in findings if f["severity"] == "red")


def test_clean_draft_no_reds():
    findings = check_consistency(CF, "Ο Παπαδόπουλος οφείλει 14.500,00 (σχετικό 1)")
    assert not [f for f in findings if f["severity"] == "red"]


def test_approve_blocked_then_allowed(auth_client):
    import time

    from tests.test_draft import _setup
    tid, case_id = _setup(auth_client)
    doc_id = auth_client.post(f"/api/cases/{case_id}/documents",
        json={"type_id": tid, "title": "Α"}).json()["id"]
    for _ in range(20):
        d = auth_client.get(f"/api/documents/{doc_id}").json()
        if d["draft"]["status"] != "running":
            break
        time.sleep(0.2)
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    assert r.status_code == 400  # open red items exist (mock draft has ΠΡΟΣ ΕΠΑΛΗΘΕΥΣΗ)
    for item in d["checklist"]:
        if item["severity"] == "red" and item["source_agent"] != "attestation":
            rr = auth_client.post(f"/api/checklist-items/{item['id']}/override",
                                  json={"note": ""})
            assert rr.status_code == 400  # empty note rejected
            auth_client.post(f"/api/checklist-items/{item['id']}/override",
                             json={"note": "ελέγχθηκε χειροκίνητα"})
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": False})
    assert r.status_code == 400
    r = auth_client.post(f"/api/documents/{doc_id}/approve", json={"attestation": True})
    assert r.status_code == 200
    assert auth_client.get(f"/api/documents/{doc_id}").json()["status"] == "approved"
