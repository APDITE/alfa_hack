from fastapi import APIRouter, HTTPException

from app.presentation import stubs
from app.presentation.schemas import (
    CompanyResponse,
    ProductId,
    ProductResponse,
    PurposeCategory,
    RecommendRequest,
    RecommendResponse,
)

router = APIRouter(tags=["catalog"])

_RECOMMENDATIONS: dict[PurposeCategory, tuple[ProductId, str]] = {
    PurposeCategory.INVENTORY: (
        ProductId.WORKING_CAPITAL,
        "Закупка товара окупается быстро — подойдёт короткий оборотный кредит без залога.",
    ),
    PurposeCategory.CASH_GAP: (
        ProductId.WORKING_CAPITAL,
        "Кассовый разрыв закрывают короткими деньгами — оборотный кредит до 24 месяцев.",
    ),
    PurposeCategory.EQUIPMENT: (
        ProductId.EQUIPMENT,
        "Оборудование служит годами — выгоднее длинный кредит с более низкой ставкой.",
    ),
    PurposeCategory.OTHER: (
        ProductId.WORKING_CAPITAL,
        "Для текущих задач бизнеса чаще всего подходит оборотный кредит.",
    ),
}


@router.get("/products", response_model=list[ProductResponse])
def list_products() -> list[ProductResponse]:
    return stubs.PRODUCTS


@router.post("/products/recommend", response_model=RecommendResponse)
def recommend_product(body: RecommendRequest) -> RecommendResponse:
    """Pick a product by the answer to "what do you need the money for?"."""
    product_id, reason = _RECOMMENDATIONS[body.purpose_category]
    return RecommendResponse(product=stubs.product_by_id(product_id), reason=reason)


@router.get("/companies/lookup/{inn}", response_model=CompanyResponse)
def lookup_company(inn: str) -> CompanyResponse:
    """Prefill company data by INN (from the EGRUL mock). Stub: any 10 or 12 digits."""
    if not inn.isdigit() or len(inn) not in (10, 12):
        raise HTTPException(422, "INN must be 10 or 12 digits")
    return stubs.SAMPLE_COMPANY.model_copy(update={"inn": inn})
