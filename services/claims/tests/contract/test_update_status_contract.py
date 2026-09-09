from fastapi.openapi.utils import get_openapi

from claims_service.main import app


def test_update_claim_status_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    operation = schema["paths"]["/claims/{claim_id}/status"]["patch"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ClaimRead"
    )
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ClaimStatusUpdate"
    )
    assert {"400", "403", "404"}.issubset(operation["responses"])