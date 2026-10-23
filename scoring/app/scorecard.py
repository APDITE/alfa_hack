import math
import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.schemas import Factor, RiskClass, ScoreRequest, ScoreResponse

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scorecard.yaml"

# при нулевой выручке отношения не определены, берём большое конечное значение
RATIO_CAP = 99.0

FEATURES = (
    "max_overdue_days",
    "overdue_count",
    "debt_load",
    "profit_margin",
    "age_months",
    "revenue_year",
    "loan_to_revenue",
    "active_loans",
    "term_months",
)


class Bin(BaseModel):
    upto: float | None
    points: int
    comment: str


class FactorConfig(BaseModel):
    feature: str
    bins: list[Bin] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> "FactorConfig":
        if self.feature not in FEATURES:
            raise ValueError(f"unknown feature: {self.feature}")
        bounds = [b.upto for b in self.bins]
        if bounds[-1] is not None:
            raise ValueError("last bin must have upto: null")
        finite = [b for b in bounds[:-1] if b is not None]
        if len(finite) != len(bounds) - 1 or finite != sorted(set(finite)):
            raise ValueError("bins must go in strictly ascending order of upto")
        return self


class PdConfig(BaseModel):
    pivot: float
    slope: float = Field(gt=0)
    min_pd: float = Field(gt=0, lt=1)
    max_pd: float = Field(gt=0, lt=1)


class RiskClassesConfig(BaseModel):
    low_max: float
    medium_max: float

    @model_validator(mode="after")
    def _check(self) -> "RiskClassesConfig":
        if not 0 < self.low_max < self.medium_max < 1:
            raise ValueError("expected 0 < low_max < medium_max < 1")
        return self


class ScorecardConfig(BaseModel):
    model_version: str
    base_points: int
    pd: PdConfig
    risk_classes: RiskClassesConfig
    factors: dict[str, FactorConfig] = Field(min_length=1)


def load_config(path: str | os.PathLike[str] | None = None) -> ScorecardConfig:
    config_path = Path(path or os.environ.get("SCORECARD_CONFIG") or DEFAULT_CONFIG_PATH)
    with config_path.open(encoding="utf-8") as f:
        return ScorecardConfig.model_validate(yaml.safe_load(f))


@lru_cache(maxsize=1)
def get_config() -> ScorecardConfig:
    return load_config()


def extract_features(req: ScoreRequest) -> dict[str, float]:
    company = req.company
    revenue = company.revenue_year
    if revenue > 0:
        debt_load = min(company.liabilities_total / revenue, RATIO_CAP)
        profit_margin = (revenue - company.expenses_year) / revenue
        loan_to_revenue = min(req.application.amount / revenue, RATIO_CAP)
    else:
        debt_load = RATIO_CAP
        profit_margin = -1.0
        loan_to_revenue = RATIO_CAP
    return {
        "max_overdue_days": req.credit_history.max_overdue_days,
        "overdue_count": req.credit_history.overdue_count,
        "debt_load": debt_load,
        "profit_margin": profit_margin,
        "age_months": company.age_months,
        "revenue_year": revenue,
        "loan_to_revenue": loan_to_revenue,
        "active_loans": req.credit_history.active_loans,
        "term_months": req.application.term_months,
    }


def _pick_bin(factor: FactorConfig, value: float) -> Bin:
    for b in factor.bins:
        if b.upto is None or value <= b.upto:
            return b
    return factor.bins[-1]


def probability_of_default(points_total: float, pd: PdConfig) -> float:
    x = pd.slope * (points_total - pd.pivot)
    # логистика через exp с защитой от переполнения
    p = 1.0 / (1.0 + math.exp(min(x, 700.0)))
    return min(max(p, pd.min_pd), pd.max_pd)


def classify(score: float, classes: RiskClassesConfig) -> RiskClass:
    if score < classes.low_max:
        return "low"
    if score < classes.medium_max:
        return "medium"
    return "high"


def score_request(req: ScoreRequest, config: ScorecardConfig | None = None) -> ScoreResponse:
    cfg = config or get_config()
    features = extract_features(req)

    factors: list[Factor] = []
    points_total = cfg.base_points
    for name, factor_cfg in cfg.factors.items():
        value = features[factor_cfg.feature]
        picked = _pick_bin(factor_cfg, value)
        points_total += picked.points
        if picked.points == 0:
            continue
        factors.append(
            Factor(
                name=name,
                points=picked.points,
                impact="decreases_risk" if picked.points > 0 else "increases_risk",
                comment=picked.comment.format(value=value),
            )
        )
    # самые влиятельные факторы первыми, при равенстве порядок из конфига
    factors.sort(key=lambda f: -abs(f.points))

    score = round(probability_of_default(points_total, cfg.pd), 4)
    return ScoreResponse(
        score=score,
        risk_class=classify(score, cfg.risk_classes),
        points_total=points_total,
        factors=factors,
        model_version=cfg.model_version,
    )
