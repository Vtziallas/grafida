from app.agents.intake_extract import run_extraction
from app.ai.mock import MockProvider


def test_quote_validation_nulls_unfound_quotes():
    # Mock returns quote "14.500,00" etc.; source lacks the amount quote
    src = "Ο Ιωάννης Παπαδόπουλος έλαβε διαταγή πληρωμής την 1/6/2026"
    out = run_extraction(MockProvider(), src)
    amounts = out["amounts"]
    assert amounts[0]["value"] is None and amounts[0]["confidence"] == 0.0
    assert out["parties"][0]["name"] == "Ιωάννης Παπαδόπουλος"  # quote found


def test_extract_endpoint_creates_facts(auth_client):
    cid = auth_client.post("/api/clients", json={"name": "Π"}).json()["id"]
    case_id = auth_client.post("/api/cases",
        json={"client_id": cid, "title": "Υ"}).json()["id"]
    auth_client.patch(f"/api/cases/{case_id}", json={
        "facts_text": "Ο Ιωάννης Παπαδόπουλος οφείλει 14.500,00 βάσει "
                      "διαταγής πληρωμής που επιδόθηκε την 1/6/2026"})
    r = auth_client.post(f"/api/cases/{case_id}/extract")
    assert r.status_code == 200
    d = r.json()
    assert len(d["parties"]) == 1 and len(d["facts"]) >= 2
    assert all(not f["confirmed"] for f in d["facts"])
