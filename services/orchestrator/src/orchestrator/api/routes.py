import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from orchestrator.auth.jwt import CurrentUser, bearer_scheme, require_roles
from orchestrator.db.session import get_db_session
from orchestrator.schemas.workflow import ClaimWorkflowCreate, WorkflowRead
from orchestrator.services.workflow_service import (
    WorkflowConflict,
    get_workflow,
    start_claim_workflow,
)

router = APIRouter()
workflow_authorization = require_roles("agent", "adjuster", "admin")


@router.post(
    "/workflows/claims",
    response_model=WorkflowRead,
    status_code=status.HTTP_201_CREATED,
    responses={400: {}, 403: {}, 409: {}},
)
async def create_workflow_endpoint(
    data: ClaimWorkflowCreate,
    session=Depends(get_db_session),
    current_user: CurrentUser = Depends(workflow_authorization),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkflowRead:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(400, "Idempotency-Key header is required")

    authorization = None
    if credentials:
        authorization = f"{credentials.scheme} {credentials.credentials}"

    try:
        return await start_claim_workflow(
            session,
            data,
            current_user.subject,
            authorization,
            idempotency_key,
        )
    except WorkflowConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
async def get_workflow_endpoint(
    workflow_id: uuid.UUID,
    session=Depends(get_db_session),
    current_user: CurrentUser = Depends(require_roles("customer", "agent", "adjuster", "admin")),
) -> WorkflowRead:
    workflow = await get_workflow(session, workflow_id)
    if workflow is None:
        raise HTTPException(404, "Workflow not found")

    if "customer" in current_user.roles and str(workflow.policyholder_id) != current_user.subject:
        raise HTTPException(404, "Workflow not found")

    return workflow
