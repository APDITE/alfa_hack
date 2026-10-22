from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app import applications as service
from app.db import SessionDep
from app.products import ProductsDep
from app.schemas import (
    AcceptOfferRequest,
    ApplicationDetail,
    ApplicationSummary,
    CreateApplicationRequest,
    ManualDecisionRequest,
    UpdateApplicationRequest,
    WithdrawRequest,
)
from app.security import CurrentUserDep
from app.statuses import ApplicationStatus, ClientStage

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
def create_application(
    body: CreateApplicationRequest, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Create a draft for the signed-in client's company."""
    application = service.create_draft(session, user, body)
    return service.to_detail(session, application, user)


@router.put("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: UUID,
    body: UpdateApplicationRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> ApplicationDetail:
    """Edit a draft, or answer a clarification request (the application goes back to review)."""
    application = service.get_for_user(session, application_id, user)
    service.update(session, user, application, body)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/submit", response_model=ApplicationDetail)
def submit_application(
    application_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    session: SessionDep,
    user: CurrentUserDep,
    products: ProductsDep,
) -> ApplicationDetail:
    """Send the draft to the bank. Repeating the call with the same key is safe."""
    application = service.submit(session, user, application_id, idempotency_key, products)
    return service.to_detail(session, application, user)


@router.get("", response_model=list[ApplicationSummary])
def list_applications(
    session: SessionDep,
    user: CurrentUserDep,
    application_status: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    client_stage: ClientStage | None = None,
) -> list[ApplicationSummary]:
    """Client: own company's applications. Employee: the queue (everything except drafts)."""
    items = service.list_for_user(session, user, application_status, client_stage)
    return [service.to_summary(session, a, user) for a in items]


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: UUID, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Full card. Checks and scoring are shown to employees only."""
    application = service.get_for_user(session, application_id, user)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/decision", response_model=ApplicationDetail)
def manual_decision(
    application_id: UUID,
    body: ManualDecisionRequest,
    session: SessionDep,
    user: CurrentUserDep,
    products: ProductsDep,
) -> ApplicationDetail:
    """Employee decision on an application in manual review."""
    application = service.get_for_user(session, application_id, user)
    service.decide_manually(session, user, application, body, products)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/accept", response_model=ApplicationDetail)
def accept_offer(
    application_id: UUID, body: AcceptOfferRequest, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Client accepts the offer (goes to signing) or declines it (withdrawn)."""
    application = service.get_for_user(session, application_id, user)
    service.respond_to_offer(session, user, application, body)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/withdraw", response_model=ApplicationDetail)
def withdraw_application(
    application_id: UUID, body: WithdrawRequest, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Client withdraws the application wherever it is their turn."""
    application = service.get_for_user(session, application_id, user)
    service.withdraw(session, user, application, body.reason)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/sign", response_model=ApplicationDetail)
def sign_documents(
    application_id: UUID, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Simulated signing and disbursement."""
    application = service.get_for_user(session, application_id, user)
    service.sign(session, user, application)
    return service.to_detail(session, application, user)
