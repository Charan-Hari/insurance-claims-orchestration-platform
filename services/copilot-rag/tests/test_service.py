import copilot_rag.main as service
from fastapi.testclient import TestClient


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_RAG_DB_PATH", str(tmp_path / "rag.db"))
    monkeypatch.setenv("COPILOT_RAG_API_KEY", "test-key")
    return TestClient(service.app)


def test_ingest_retrieve_grounded_draft_and_human_boundary(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {"X-API-Key": "test-key", "X-Request-ID": "req-1"}
    assert c.get("/health").json()["status"] == "ok"
    ingested = c.post("/knowledge", headers=headers, json={
        "title": "Property policy", "content": "Water damage coverage limit is 5000.",
        "policy_id": "POL-1"})
    assert ingested.status_code == 201
    draft = c.post("/drafts", headers=headers, json={"question": "What is the water damage limit?",
                                                     "policy_id": "POL-1"})
    assert draft.status_code == 201
    body = draft.json()
    assert body["citations"] and body["approval_required"] is True
    assert "not an adjudication" in body["disclaimer"]
    assert draft.headers["X-Request-ID"] == "req-1"
    approved = c.post(f"/drafts/{body['id']}/approval", headers=headers,
                      json={"approved": True, "note": "Reviewed"})
    assert approved.json()["status"] == "approved"


def test_auth_and_policy_scope(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get("/retrieve?q=limit").status_code == 401
    h = {"X-API-Key": "test-key"}
    c.post("/knowledge", headers=h, json={"title": "A", "content": "limit 1", "policy_id": "P1"})
    assert c.get("/retrieve?q=limit&policy_id=P2", headers=h).json()["results"] == []
