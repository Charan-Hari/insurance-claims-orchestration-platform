from fastapi.openapi.utils import get_openapi

from policy_service.main import app


def test_update_policy_status_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    operation = schema["paths"]["/policies/{policy_id}/status"]["patch"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PolicyRead"
    )
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"] == "#/components/schemas/PolicyStatusUpdate"
    assert {"400", "403", "404"}.issubset(operation["responses"])