import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/orchestrator_db")
os.environ.setdefault("POLICY_SERVICE_BASE_URL", "http://policy-service:8000")
os.environ.setdefault("CLAIMS_SERVICE_BASE_URL", "http://claims-service:8000")
os.environ.setdefault("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/policy")

from fastapi.openapi.utils import get_openapi

from orchestrator.main import app


def test_workflow_endpoints_are_documented() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    assert "/workflows/claims" in schema["paths"]
    assert "/workflows/{workflow_id}" in schema["paths"]
    assert "post" in schema["paths"]["/workflows/claims"]
    assert "get" in schema["paths"]["/workflows/{workflow_id}"]
    assert "/workflows/{workflow_id}/retry" in schema["paths"]
    assert "post" in schema["paths"]["/workflows/{workflow_id}/retry"]
    workflow_state = schema["components"]["schemas"]["WorkflowState"]["enum"]
    assert "reconciliation_required" in workflow_state
