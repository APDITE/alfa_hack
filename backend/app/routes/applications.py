from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app import applications as service
from app import cash_plans
from app.db import SessionDep
from app.products import ProductsDep
from app.schemas import (
    AcceptOfferRequest,
    AgreementDocument,
    ApplicationDetail,
    ApplicationSummary,
    CashPlanRequest,
    CashPreviewRequest,
    CashPreviewResponse,
    CreateApplicationRequest,
    ManualDecisionRequest,
    ProposalRequest,
    SignRequest,
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


@router.post("/{application_id}/proposals", response_model=ApplicationDetail)
def propose_terms(
    application_id: UUID,
    body: ProposalRequest,
    session: SessionDep,
    user: CurrentUserDep,
    products: ProductsDep,
) -> ApplicationDetail:
    """Client answers the bank's offer with their own terms (a negotiation round); the
    application goes back to an employee."""
    application = service.get_for_user(session, application_id, user)
    service.propose(session, user, application, body, products)
    return service.to_detail(session, application, user)


@router.get("/{application_id}/agreement", response_model=AgreementDocument)
def get_agreement(
    application_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
    version: int | None = Query(default=None, ge=1, description="Latest if omitted"),
) -> AgreementDocument:
    """The loan agreement text with its SHA-256 and a check that the text still matches it."""
    application = service.get_for_user(session, application_id, user)
    return service.agreement_document(session, application, version)


@router.post("/{application_id}/sign", response_model=ApplicationDetail)
def sign_documents(
    application_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
    body: SignRequest | None = None,
) -> ApplicationDetail:
    """Simulated signing and disbursement. With `agreement_sha256`, nothing is signed if the
    agreement has changed since the client read it (409)."""
    application = service.get_for_user(session, application_id, user)
    service.sign(session, user, application, body)
    return service.to_detail(session, application, user)


@router.post("/{application_id}/cash-calendar/preview", response_model=CashPreviewResponse)
def preview_cash_calendar(
    application_id: UUID, body: CashPreviewRequest, session: SessionDep, user: CurrentUserDep
) -> CashPreviewResponse:
    """Compare payment days against the client's cash flow, as planned and with receipts a week
    late; nothing is saved. Without a calendar: the saved one or a template from revenue."""
    application = service.get_for_user(session, application_id, user)
    return cash_plans.preview(session, user, application, body)


@router.put("/{application_id}/cash-calendar", response_model=ApplicationDetail)
def save_cash_calendar(
    application_id: UUID, body: CashPlanRequest, session: SessionDep, user: CurrentUserDep
) -> ApplicationDetail:
    """Save the client's typical month and the payment day; the schedule gets dates."""
    application = service.get_for_user(session, application_id, user)
    cash_plans.save(session, user, application, body)
    return service.to_detail(session, application, user)
