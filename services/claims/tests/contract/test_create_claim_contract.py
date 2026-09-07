from fastapi.openapi.utils import get_openapi

from claims_service.main import app


def test_create_claim_openapi_contract() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    operation = schema["paths"]["/claims"]["post"]

    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ClaimRead"
    )
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ClaimCreate"
    )
    assert {"400", "403", "503"}.issubset(operation["responses"])