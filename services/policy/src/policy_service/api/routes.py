from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from policy_service.auth.jwt import CurrentUser, require_roles
from policy_service.db.session import get_db_session
from policy_service.schemas.policy import PolicyCreate, PolicyRead
from policy_service.services.policy_service import create_policy

router = APIRouter()
create_policy_authorization = require_roles("agent", "underwriter")


@router.post("/policies", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy_endpoint(
	policy_data: PolicyCreate,
	session: AsyncSession = Depends(get_db_session),
	_: CurrentUser = Depends(create_policy_authorization),
) -> PolicyRead:
	return await create_policy(session, policy_data)