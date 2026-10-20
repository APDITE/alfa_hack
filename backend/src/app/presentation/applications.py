from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, status

from app.domain.application_status import ApplicationStatus, ClientStage
from app.presentation import stubs
from app.presentation.schemas import (
    AcceptOfferRequest,
    ApplicationDetail,
    ApplicationSummary,
    CreateApplicationRequest,
    DecisionOutcome,
    ManualDecisionRequest,
    UpdateApplicationRequest,
    WithdrawRequest,
)

router = APIRouter(prefix="/applications", tags=["applications"])

S = ApplicationStatus

_OUTCOME_STATUS: dict[DecisionOutcome, ApplicationStatus] = {
    DecisionOutcome.APPROVED: S.APPROVED,
    DecisionOutcome.COUNTER_OFFER: S.COUNTER_OFFER,
    DecisionOutcome.CLARIFICATION: S.CLARIFICATION_REQUIRED,
    DecisionOutcome.REJECTED: S.REJECTED,
}


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_application(body: CreateApplicationRequest) -> ApplicationDetail:
    """Create a draft. Company data is taken from the signed-in client's company."""
    draft = stubs.sample_application(uuid4(), S.DRAFT)
    return draft.model_copy(update=body.model_dump(exclude_none=True))


@router.put("/{application_id}", response_model=ApplicationDetail)
def update_application(application_id: UUID, body: UpdateApplicationRequest) -> ApplicationDetail:
    """Edit a draft, or answer a clarification request (the application goes back to review)."""
    detail = stubs.sample_application(application_id, S.DRAFT)
    fields = body.model_dump(exclude_none=True, include=set(ApplicationDetail.model_fields))
    return detail.model_copy(update=fields)


@router.post("/{application_id}/submit", response_model=ApplicationDetail)
def submit_application(
    application_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ApplicationDetail:
    """Send the draft for processing. Repeating the call with the same key is safe."""
    return stubs.sample_application(application_id, S.SUBMITTED)


@router.get("", response_model=list[ApplicationSummary])
def list_applications(
    application_status: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    client_stage: ClientStage | None = None,
) -> list[ApplicationSummary]:
    """Client: own applications. Employee: the queue, filterable by status or stage."""
    statuses = [S.MANUAL_REVIEW, S.APPROVED, S.CLARIFICATION_REQUIRED]
    items = [
        stubs.summary_of(stubs.sample_application(UUID(int=i + 1), s, for_employee=True))
        for i, s in enumerate(statuses)
    ]
    if application_status is not None:
        items = [i for i in items if i.status is application_status]
    if client_stage is not None:
        items = [i for i in items if i.client_stage is client_stage]
    return items


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: UUID) -> ApplicationDetail:
    """Full card: data, status, history, checks and scoring (checks and scoring: employee only)."""
    return stubs.sample_application(application_id, S.APPROVED, for_employee=True)


@router.post("/{application_id}/decision", response_model=ApplicationDetail)
def manual_decision(application_id: UUID, body: ManualDecisionRequest) -> ApplicationDetail:
    """Employee decision on an application in manual review."""
    return stubs.sample_application(
        application_id, _OUTCOME_STATUS[body.outcome], for_employee=True
    )


@router.post("/{application_id}/accept", response_model=ApplicationDetail)
def accept_offer(application_id: UUID, body: AcceptOfferRequest) -> ApplicationDetail:
    """Client accepts the offer (goes to signing) or declines it (withdrawn)."""
    return stubs.sample_application(application_id, S.SIGNING if body.accept else S.WITHDRAWN)


@router.post("/{application_id}/withdraw", response_model=ApplicationDetail)
def withdraw_application(application_id: UUID, body: WithdrawRequest) -> ApplicationDetail:
    """Client withdraws the application wherever it is their turn."""
    return stubs.sample_application(application_id, S.WITHDRAWN)


@router.post("/{application_id}/sign", response_model=ApplicationDetail)
def sign_documents(application_id: UUID) -> ApplicationDetail:
    """Simulated signing and disbursement."""
    return stubs.sample_application(application_id, S.ISSUED)
