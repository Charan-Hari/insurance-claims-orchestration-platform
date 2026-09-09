from fastapi.openapi.utils import get_openapi

from claims_service.main import app


def test_get_claim_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    get_operation = schema["paths"]["/claims/{claim_id}"]["get"]
    assert get_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ClaimRead"
    )
    assert get_operation["parameters"][0]["name"] == "claim_id"

    list_operation = schema["paths"]["/policyholders/{policyholder_id}/claims"]["get"]
    list_schema = list_operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert list_schema["type"] == "array"
    assert list_schema["items"]["$ref"] == "#/components/schemas/ClaimRead"