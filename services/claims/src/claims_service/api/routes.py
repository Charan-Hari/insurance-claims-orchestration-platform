import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from claims_service.auth.jwt import CurrentUser, bearer_scheme, require_roles
from claims_service.db.session import get_db_session
from claims_service.schemas.claim import ClaimCreate, ClaimRead
from claims_service.services.claim_service import create_claim
from claims_service.services.policy_client import PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable


router = APIRouter()
create_claim_authorization = require_roles("agent", "adjuster")


@router.post(
	"/claims",
	response_model=ClaimRead,
	status_code=status.HTTP_201_CREATED,
	responses={
		400: {"description": "Policy validation failed"},
		403: {"description": "Access denied"},
		503: {"description": "Policy Service unavailable"},
	},
)
async def create_claim_endpoint(
	claim_data: ClaimCreate,
	session: AsyncSession = Depends(get_db_session),
	current_user: CurrentUser = Depends(create_claim_authorization),
	credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ClaimRead:
	authorization = None
	if credentials is not None:
		authorization = f"{credentials.scheme} {credentials.credentials}"
	try:
		return await create_claim(session, claim_data, authorization)
	except (PolicyNotFound, PolicyNotActive) as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
	except PolicyServiceUnavailable as exc:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc