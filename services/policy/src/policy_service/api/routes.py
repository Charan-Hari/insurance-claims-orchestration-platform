import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from policy_service.auth.jwt import CurrentUser, require_roles
from policy_service.db.session import get_db_session
from policy_service.schemas.policy import PolicyCreate, PolicyRead, PolicyStatusUpdate
from policy_service.services.policy_service import (
	can_view_policy,
	can_view_policyholder,
	create_policy,
	get_policy_by_id,
	InvalidStatusTransition,
	list_policies_for_policyholder,
	update_policy_status,
)

router = APIRouter()
logger = logging.getLogger("policy_service")
create_policy_authorization = require_roles("agent", "underwriter")
retrieve_policy_authorization = require_roles("customer", "admin", "agent", "underwriter")
update_status_authorization = require_roles("underwriter", "admin")


@router.post("/policies", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy_endpoint(
	policy_data: PolicyCreate,
	session: AsyncSession = Depends(get_db_session),
	current_user: CurrentUser = Depends(create_policy_authorization),
) -> PolicyRead:
	policy = await create_policy(session, policy_data)
	logger.info(
		"create_policy",
		extra={
			"action": "create_policy",
			"actor_id": current_user.subject,
			"policy_id": str(policy.id),
		},
	)
	return policy


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


@router.patch(
	"/policies/{policy_id}/status",
	response_model=PolicyRead,
	responses={
		400: {"description": "Invalid status transition"},
		403: {"description": "Access denied"},
		404: {"description": "Policy not found"},
	},
)
async def update_policy_status_endpoint(
	policy_id: uuid.UUID,
	status_update: PolicyStatusUpdate,
	session: AsyncSession = Depends(get_db_session),
	current_user: CurrentUser = Depends(update_status_authorization),
) -> PolicyRead:
	try:
		policy = await update_policy_status(session, policy_id, status_update.status, current_user.subject)
	except InvalidStatusTransition as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
	if policy is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
	return policy