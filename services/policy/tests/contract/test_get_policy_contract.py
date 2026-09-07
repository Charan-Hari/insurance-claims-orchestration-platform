from fastapi.openapi.utils import get_openapi

from policy_service.main import app


def test_get_policy_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    get_operation = schema["paths"]["/policies/{policy_id}"]["get"]
    assert get_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PolicyRead"
    )
    assert get_operation["parameters"][0]["name"] == "policy_id"
    assert get_operation["parameters"][0]["required"] is True

    list_operation = schema["paths"]["/policyholders/{policyholder_id}/policies"]["get"]
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert list_operation["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"] == (
        "#/components/schemas/PolicyRead"
    )