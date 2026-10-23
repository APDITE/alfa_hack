import copy

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import ScoreRequest
from app.scorecard import DEFAULT_CONFIG_PATH, ScorecardConfig, score_request

STRONG = {
    "application": {"product_id": "working_capital", "amount": 1_500_000, "term_months": 12},
    "company": {
        "inn": "7700000001", "okved": "47.11", "age_months": 79,
        "revenue_year": 48_000_000, "expenses_year": 40_000_000, "liabilities_total": 4_000_000,
    },
    "credit_history": {"active_loans": 1, "overdue_count": 0, "max_overdue_days": 0},
}


def make(**overrides) -> dict:
    payload = copy.deepcopy(STRONG)
    for path, value in overrides.items():
        section, key = path.split("__")
        payload[section][key] = value
    return payload


def score(payload: dict):
    return score_request(ScoreRequest.model_validate(payload))


def load_raw_config() -> dict:
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def test_strong_company_gets_low_risk():
    result = score(STRONG)
    assert result.risk_class == "low"
    assert result.score < 0.10


def test_overdue_90_plus_gets_high_risk():
    result = score(make(credit_history__max_overdue_days=95, credit_history__overdue_count=5))
    assert result.risk_class == "high"
    assert result.score >= 0.25
    assert any(f.name == "credit_history" and f.impact == "increases_risk" for f in result.factors)


def test_same_input_gives_same_output():
    assert score(STRONG) == score(copy.deepcopy(STRONG))


def test_score_is_probability_and_points_are_consistent():
    result = score(STRONG)
    assert 0 < result.score < 1
    config = ScorecardConfig.model_validate(load_raw_config())
    assert result.points_total == config.base_points + sum(f.points for f in result.factors)


def test_factor_impact_matches_points_sign():
    result = score(make(credit_history__max_overdue_days=45))
    assert result.factors
    for f in result.factors:
        assert f.points != 0
        assert (f.impact == "decreases_risk") == (f.points > 0)
        assert f.comment


def test_factors_sorted_by_influence():
    result = score(make(credit_history__max_overdue_days=95))
    weights = [abs(f.points) for f in result.factors]
    assert weights == sorted(weights, reverse=True)


def test_more_overdue_days_never_lowers_risk():
    scores = [score(make(credit_history__max_overdue_days=d)).score for d in (0, 10, 60, 120)]
    assert scores == sorted(scores)


def test_bigger_amount_raises_risk():
    small = score(make(application__amount=1_000_000)).score
    big = score(make(application__amount=30_000_000)).score
    assert big > small


def test_score_does_not_depend_on_product():
    a = score(make(application__product_id="working_capital"))
    b = score(make(application__product_id="equipment"))
    assert a.score == b.score and a.points_total == b.points_total


def test_zero_revenue_does_not_crash_and_is_risky():
    result = score(make(company__revenue_year=0, company__expenses_year=0))
    assert result.risk_class == "high"


def test_contract_over_http():
    client = TestClient(app)
    response = client.post("/score", json=STRONG)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"score", "risk_class", "points_total", "factors", "model_version"}
    assert body["model_version"] == "scorecard-0.1.0"
    assert set(body["factors"][0]) == {"name", "points", "impact", "comment"}


def test_extra_fields_are_ignored():
    payload = make()
    payload["application"]["purpose"] = "пополнение оборотных средств"
    assert TestClient(app).post("/score", json=payload).status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"application__product_id": "mortgage"},
        {"application__amount": -5},
        {"application__term_months": 0},
        {"company__inn": "abc"},
        {"company__age_months": -1},
        {"credit_history__overdue_count": -1},
    ],
)
def test_invalid_input_is_rejected(overrides):
    assert TestClient(app).post("/score", json=make(**overrides)).status_code == 422


def test_missing_section_is_rejected():
    payload = copy.deepcopy(STRONG)
    del payload["credit_history"]
    assert TestClient(app).post("/score", json=payload).status_code == 422


def test_health():
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_broken_config_is_rejected():
    raw = load_raw_config()
    raw["factors"]["debt_load"]["bins"][-1]["upto"] = 5  # последний интервал обязан быть открытым
    with pytest.raises(ValidationError):
        ScorecardConfig.model_validate(raw)
    raw = load_raw_config()
    raw["factors"]["debt_load"]["feature"] = "nonsense"
    with pytest.raises(ValidationError):
        ScorecardConfig.model_validate(raw)
