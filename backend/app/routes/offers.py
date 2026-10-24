from fastapi import APIRouter, HTTPException, status

from app import applications, preapproval
from app.db import SessionDep
from app.integrations import ExternalUnavailableError, IntegrationsDep
from app.models import Company
from app.products import ProductsDep
from app.schemas import LoanTerms, PreapprovalResponse, ProductId
from app.security import CurrentUserDep

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("/preapproved", response_model=PreapprovalResponse)
def preapproved_offers(
    session: SessionDep,
    user: CurrentUserDep,
    integrations: IntegrationsDep,
    products: ProductsDep,
) -> PreapprovalResponse:
    """What the bank would approve automatically right now, per product (clients only).

    The same sources and credit rules as the pipeline; nothing is stored. An application
    with these terms gets the same decision while the company's data does not change.
    """
    inn = applications.require_client(user)
    company = session.get(Company, inn)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    try:
        result = preapproval.preapprove(integrations, products, company)
    except ExternalUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "External service is temporarily unavailable"
        ) from exc
    return PreapprovalResponse(
        offers=[
            LoanTerms(
                product_id=ProductId(offer.product_id),
                amount=offer.amount,
                term_months=offer.term_months,
                rate=offer.rate,
                monthly_payment=offer.monthly_payment,
            )
            for offer in result.offers
        ],
        reason=result.reason,
    )
