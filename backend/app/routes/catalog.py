from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.db import SessionDep
from app.models import Company, Product
from app.schemas import (
    CompanyResponse,
    LegalForm,
    ProductId,
    ProductResponse,
    PurposeCategory,
    RecommendRequest,
    RecommendResponse,
)
from app.security import get_current_user

router = APIRouter(tags=["catalog"])

_REASONS: dict[PurposeCategory, str] = {
    PurposeCategory.INVENTORY: (
        "Закупка товара окупается быстро — подойдёт короткий оборотный кредит без залога."
    ),
    PurposeCategory.CASH_GAP: (
        "Кассовый разрыв закрывают короткими деньгами — оборотный кредит до 24 месяцев."
    ),
    PurposeCategory.EQUIPMENT: (
        "Оборудование служит годами — выгоднее длинный кредит с более низкой ставкой."
    ),
    PurposeCategory.OTHER: "Для текущих задач бизнеса чаще всего подходит оборотный кредит.",
}


def _to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=ProductId(p.id),
        name=p.name,
        description=p.description,
        purposes=[PurposeCategory(x) for x in p.purposes],
        min_amount=p.min_amount,
        max_amount=p.max_amount,
        min_term_months=p.min_term_months,
        max_term_months=p.max_term_months,
        base_rate=p.base_rate,
        min_business_age_months=p.min_business_age_months,
    )


@router.get("/products", response_model=list[ProductResponse])
def list_products(session: SessionDep) -> list[ProductResponse]:
    products = session.scalars(select(Product).order_by(Product.base_rate.desc())).all()
    return [_to_response(p) for p in products]


@router.post("/products/recommend", response_model=RecommendResponse)
def recommend_product(body: RecommendRequest, session: SessionDep) -> RecommendResponse:
    """Pick a product by the answer to "what do you need the money for?"."""
    products = session.scalars(select(Product).order_by(Product.base_rate.desc())).all()
    match = next((p for p in products if body.purpose_category in p.purposes), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No product for this purpose")
    return RecommendResponse(product=_to_response(match), reason=_REASONS[body.purpose_category])


@router.get(
    "/companies/lookup/{inn}",
    response_model=CompanyResponse,
    dependencies=[Depends(get_current_user)],
)
def lookup_company(inn: str, session: SessionDep) -> CompanyResponse:
    """Prefill company data by INN (signed-in users). Demo companies: 7700000001 … 7700000008."""
    if not inn.isdigit() or len(inn) not in (10, 12):
        raise HTTPException(422, "INN must be 10 or 12 digits")
    company = session.get(Company, inn)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found in the registry")
    return CompanyResponse(
        inn=company.inn,
        name=company.name,
        legal_form=LegalForm(company.legal_form),
        okved=company.okved,
        registration_date=company.registration_date,
        region=company.region,
        director=company.director,
    )
