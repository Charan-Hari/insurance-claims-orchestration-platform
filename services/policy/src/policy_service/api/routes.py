import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from policy_service.auth.jwt import CurrentUser, require_roles
from policy_service.db.session import get_db_session
from policy_service.schemas.policy import PolicyCreate, PolicyRead
from policy_service.services.policy_service import (
	can_view_policy,
	can_view_policyholder,
	create_policy,
	get_policy_by_id,
	list_policies_for_policyholder,
)

router = APIRouter()
create_policy_authorization = require_roles("agent", "underwriter")
retrieve_policy_authorization = require_roles("customer", "admin", "agent", "underwriter")


@router.post("/policies", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy_endpoint(
	policy_data: PolicyCreate,
	session: AsyncSession = Depends(get_db_session),
	_: CurrentUser = Depends(create_policy_authorization),
) -> PolicyRead:
	return await create_policy(session, policy_data)


@router.get("/policies/{policy_id}", response_model=PolicyRead)
async def get_policy_endpoint(
	policy_id: uuid.UUID,
	session: AsyncSession = Depends(get_db_session),
	current_user: CurrentUser = Depends(retrieve_policy_authorization),
) -> PolicyRead:
	policy = await get_policy_by_id(session, policy_id)
	if policy is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
	if not can_view_policy(policy, current_user):
		if "customer" in current_user.roles:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
	return policy


@router.get("/policyholders/{policyholder_id}/policies", response_model=list[PolicyRead])
async def list_policies_endpoint(
	policyholder_id: uuid.UUID,
	session: AsyncSession = Depends(get_db_session),
	current_user: CurrentUser = Depends(retrieve_policy_authorization),
) -> list[PolicyRead]:
	if not can_view_policyholder(policyholder_id, current_user):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
	return await list_policies_for_policyholder(session, policyholder_id)