from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProductId = Literal["working_capital", "equipment"]
RiskClass = Literal["low", "medium", "high"]
Impact = Literal["decreases_risk", "increases_risk"]


class _Input(BaseModel):
    # лишние поля (например purpose) не ломают контракт
    model_config = ConfigDict(extra="ignore")


class ApplicationIn(_Input):
    product_id: ProductId
    amount: float = Field(gt=0)
    term_months: int = Field(gt=0, le=120)


class CompanyIn(_Input):
    inn: str = Field(min_length=10, max_length=12, pattern=r"^\d+$")
    okved: str = Field(min_length=1, max_length=16)
    age_months: int = Field(ge=0)
    revenue_year: float = Field(ge=0)
    expenses_year: float = Field(ge=0)
    liabilities_total: float = Field(ge=0)


class CreditHistoryIn(_Input):
    active_loans: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    max_overdue_days: int = Field(ge=0)


class ScoreRequest(_Input):
    application: ApplicationIn
    company: CompanyIn
    credit_history: CreditHistoryIn


class Factor(BaseModel):
    name: str
    points: int
    impact: Impact
    comment: str


class ScoreResponse(BaseModel):
    score: float
    risk_class: RiskClass
    points_total: int
    factors: list[Factor]
    model_version: str
