"""TEMPORARY sample data so the frontend can work against the real contract.

Delete this module once handlers call real use cases.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.domain.application_status import CLIENT_STAGE, Actor, ApplicationStatus
from app.presentation.labels import NEXT_STEPS, STAGE_LABELS, STATUS_LABELS
from app.presentation.schemas import (
    ApplicationDetail,
    ApplicationSummary,
    CheckOutcome,
    CheckResult,
    CheckType,
    CompanyResponse,
    DecisionOutcome,
    DecisionView,
    FactorImpact,
    FeedItem,
    FeedItemType,
    LegalForm,
    LoanTerms,
    ProductId,
    ProductResponse,
    PurposeCategory,
    RiskClass,
    ScoreFactor,
    ScoreView,
    StatusHistoryItem,
    UserResponse,
    UserRole,
)

S = ApplicationStatus
NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
SAMPLE_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000001")

CLIENT_USER = UserResponse(
    id=UUID("00000000-0000-0000-0000-0000000000c1"),
    login="client1",
    full_name="Анна Смирнова",
    role=UserRole.CLIENT,
    company_inn="7700000001",
)
EMPLOYEE_USER = UserResponse(
    id=UUID("00000000-0000-0000-0000-0000000000e1"),
    login="analyst",
    full_name="Пётр Кузнецов",
    role=UserRole.EMPLOYEE,
)

PRODUCTS: list[ProductResponse] = [
    ProductResponse(
        id=ProductId.WORKING_CAPITAL,
        name="Оборотный кредит",
        description="Деньги на закупку товара, зарплаты и текущие расходы. "
        "Без залога, решение по типовым заявкам — автоматически.",
        purposes=[PurposeCategory.INVENTORY, PurposeCategory.CASH_GAP, PurposeCategory.OTHER],
        min_amount=300_000,
        max_amount=10_000_000,
        min_term_months=3,
        max_term_months=24,
        base_rate=19.5,
        min_business_age_months=6,
    ),
    ProductResponse(
        id=ProductId.EQUIPMENT,
        name="Кредит на оборудование",
        description="Покупка оборудования и техники на срок до пяти лет. "
        "Ставка ниже, но бизнесу должно быть не меньше года.",
        purposes=[PurposeCategory.EQUIPMENT],
        min_amount=1_000_000,
        max_amount=30_000_000,
        min_term_months=12,
        max_term_months=60,
        base_rate=16.5,
        min_business_age_months=12,
    ),
]

SAMPLE_COMPANY = CompanyResponse(
    inn="7700000001",
    name="ООО «Северный ветер»",
    legal_form=LegalForm.OOO,
    okved="47.11",
    registration_date=date(2021, 3, 15),
    region="77",
    director="Смирнова А. В.",
)

SAMPLE_SCORE = ScoreView(
    score=0.08,
    risk_class=RiskClass.LOW,
    points_total=612,
    factors=[
        ScoreFactor(
            name="credit_history",
            points=120,
            impact=FactorImpact.DECREASES_RISK,
            comment="Просрочек нет",
        ),
        ScoreFactor(
            name="debt_load",
            points=35,
            impact=FactorImpact.INCREASES_RISK,
            comment="Обязательства составляют заметную долю выручки",
        ),
    ],
    model_version="scorecard-0.1.0",
)


def product_by_id(product_id: ProductId) -> ProductResponse:
    return next(p for p in PRODUCTS if p.id is product_id)


def sample_application(
    application_id: UUID = SAMPLE_APPLICATION_ID,
    status: ApplicationStatus = S.APPROVED,
    *,
    for_employee: bool = False,
) -> ApplicationDetail:
    stage = CLIENT_STAGE[status]
    decided = status in {S.APPROVED, S.SIGNING, S.ISSUED}
    return ApplicationDetail(
        id=application_id,
        status=status,
        status_label=STATUS_LABELS[status],
        client_stage=stage,
        stage_label=STAGE_LABELS[stage],
        product_id=ProductId.WORKING_CAPITAL,
        amount=1_500_000,
        term_months=12,
        company_inn=SAMPLE_COMPANY.inn,
        company_name=SAMPLE_COMPANY.name,
        risk_class=RiskClass.LOW if for_employee else None,
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW,
        purpose_category=PurposeCategory.INVENTORY,
        purpose="Закупка товара к сезону",
        next_step=NEXT_STEPS[status],
        waiting_external=False,
        company=SAMPLE_COMPANY,
        history=[
            StatusHistoryItem(
                from_status=None, to_status=S.DRAFT, actor=Actor.CLIENT, at=NOW - timedelta(hours=1)
            ),
            StatusHistoryItem(
                from_status=S.DRAFT,
                to_status=S.SUBMITTED,
                actor=Actor.CLIENT,
                at=NOW - timedelta(minutes=50),
            ),
        ],
        checks=[
            CheckResult(type=CheckType.COMPLETENESS, outcome=CheckOutcome.PASSED, summary="OK"),
            CheckResult(
                type=CheckType.EGRUL, outcome=CheckOutcome.PASSED, summary="Компания действует"
            ),
            CheckResult(type=CheckType.BKI, outcome=CheckOutcome.PASSED, summary="Просрочек нет"),
        ]
        if for_employee
        else [],
        score=SAMPLE_SCORE if for_employee else None,
        decision=DecisionView(
            outcome=DecisionOutcome.APPROVED,
            terms=LoanTerms(
                product_id=ProductId.WORKING_CAPITAL,
                amount=1_500_000,
                term_months=12,
                rate=19.5,
                monthly_payment=138_700,
            ),
            reason="Финансовое положение компании устойчивое, просрочек нет.",
            rule="auto_approve",
            decided_by=Actor.SYSTEM,
            decided_at=NOW,
        )
        if decided
        else None,
    )


def summary_of(detail: ApplicationDetail) -> ApplicationSummary:
    return ApplicationSummary.model_validate(
        detail.model_dump(include=set(ApplicationSummary.model_fields))
    )


SAMPLE_FEED: list[FeedItem] = [
    FeedItem(
        id=UUID("00000000-0000-0000-0000-0000000000f1"),
        type=FeedItemType.EVENT,
        title="Решение готово",
        text="Банк одобрил заявку на 1 500 000 ₽ на 12 месяцев.",
        application_id=SAMPLE_APPLICATION_ID,
        created_at=NOW,
        read=False,
    ),
    FeedItem(
        id=UUID("00000000-0000-0000-0000-0000000000f2"),
        type=FeedItemType.NEWS,
        title="Сниженная ставка для розницы",
        text="Для магазинов (ОКВЭД 47) оборотный кредит до конца года — от 17,9%.",
        created_at=NOW - timedelta(days=1),
        read=True,
    ),
]
