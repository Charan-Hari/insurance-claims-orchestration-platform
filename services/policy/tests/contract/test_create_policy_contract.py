from fastapi.openapi.utils import get_openapi

from policy_service.main import app


def test_create_policy_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    operation = schema["paths"]["/policies"]["post"]

    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PolicyRead"
    )
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"] == "#/components/schemas/PolicyCreate"
    assert set(schema["components"]["schemas"]["PolicyCreate"]["required"]) == {
        "policyholder_id",
        "coverage_type",
        "coverage_limits",
        "effective_date",
        "expiry_date",
    }