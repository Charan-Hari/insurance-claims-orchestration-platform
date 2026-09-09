import hashlib

from fastapi.testclient import TestClient

from document_intelligence.main import app


def test_upload_idempotency_review_and_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("DOCUMENT_INTELLIGENCE_API_KEY", "test-key")
    client = TestClient(app)
    headers = {"X-API-Key": "test-key", "Idempotency-Key": "same-upload"}
    content = b"claim form: missing signature"
    response = client.post(
        "/documents?claim_id=CL-1&policy_id=POL-1",
        files={"file": ("claim.txt", content, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    document = response.json()
    assert document["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    duplicate = client.post(
        "/documents?claim_id=CL-1&policy_id=POL-1",
        files={"file": ("different-name.txt", content, "text/plain")},
        headers=headers,
    )
    assert duplicate.status_code in (200, 201)
    assert duplicate.json()["id"] == document["id"]

    recommendation = client.post(f"/documents/{document['id']}/reviews", headers={"X-API-Key": "test-key"})
    assert recommendation.status_code == 201
    review = recommendation.json()
    assert review["status"] == "pending"
    assert "Signature appears to be missing" in review["reasons"]
    decision = client.post(
        f"/documents/reviews/{review['id']}/approval",
        json={"approved": False, "note": "Please obtain signed form"},
        headers={"X-API-Key": "test-key"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"


def test_auth_and_safe_retrieval(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("DOCUMENT_INTELLIGENCE_API_KEY", "test-key")
    client = TestClient(app)
    assert client.get("/documents").status_code == 401
    upload = client.post(
        "/documents",
        files={"file": ("..\\outside.txt", b"safe", "text/plain")},
        headers={"X-API-Key": "test-key"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    retrieved = client.get(f"/documents/{document_id}/content", headers={"X-API-Key": "test-key"})
    assert retrieved.status_code == 200
    assert retrieved.content == b"safe"
