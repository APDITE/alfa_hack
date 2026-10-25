"""Cash calendar: gaps in the client's cash flow, receipts a week late, the price of a later
payment day, and the API that saves the choice and dates the payment schedule."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import cash_calendar as cc
from app.credit_decision import annuity_payment
from app.pipeline import PipelineContext, run_until_idle
from app.schedule import annuity_schedule, first_period_interest, payment_dates
from test_pipeline import FakeIntegrations

LoginAs = Callable[[str], dict[str, str]]

ISSUE = date(2026, 10, 25)
PAYMENT = annuity_payment(5_000_000, 19.5, 24)


def month(*events: tuple[int, int], opening: int = 0, reserve: int = 0) -> cc.CashCalendar:
    return cc.CashCalendar(opening, reserve, tuple(cc.CashEvent(d, a) for d, a in events))


def test_a_payment_due_in_the_morning_is_not_covered_by_the_evening_receipt() -> None:
    sim = cc.simulate(month((10, 1_000), opening=100), [(date(2026, 11, 10), 500)])
    assert (sim.min_balance, sim.first_gap, sim.shortfall) == (-400, date(2026, 11, 10), 400)


def test_receipts_a_week_late_open_a_gap() -> None:
    calendar = month((5, 1_000))
    payments = [(date(2026, 11, 10), 800)]
    assert cc.simulate(calendar, payments).first_gap is None
    late = cc.simulate(calendar, payments, cc.DELAY_DAYS)
    assert (late.first_gap, late.shortfall) == (date(2026, 11, 10), 800)


def test_reserve_and_short_months() -> None:
    # A payment "on the 31st" happens on the last day of February.
    sim = cc.simulate(month((31, -100), opening=250, reserve=200), [(date(2027, 2, 28), 0)])
    assert (sim.min_date, sim.first_gap, sim.shortfall) == (
        date(2027, 2, 28),
        date(2027, 2, 28),
        50,
    )


def test_payment_days() -> None:
    assert payment_dates(date(2026, 1, 31), 28, 3) == [
        date(2026, 2, 28),
        date(2026, 3, 28),
        date(2026, 4, 28),
    ]
    with pytest.raises(ValueError):
        payment_dates(ISSUE, 29, 3)


def test_dated_schedule_charges_the_first_period_by_days() -> None:
    plain = annuity_schedule(5_000_000, 19.5, 24, PAYMENT)
    dated = annuity_schedule(5_000_000, 19.5, 24, PAYMENT, ISSUE, 28)
    first_interest = first_period_interest(5_000_000, 19.5, ISSUE, date(2026, 11, 28))
    assert dated[0].due_date == date(2026, 11, 28) and dated[-1].due_date == date(2028, 10, 28)
    assert dated[0].interest == first_interest  # 34 days instead of a month
    assert [p.principal for p in dated] == [p.principal for p in plain]
    # Dates aside, every later payment is the same as without a chosen day.
    assert [p.payment for p in dated[1:]] == [p.payment for p in plain[1:]]


def test_later_day_avoids_the_gap_but_costs_interest() -> None:
    """Client1's month: salaries on the 5th, suppliers on the 20th, buyers pay on the
    10th and the 25th. Any day before the 25th receipt opens a gap; the 28th does not, but
    is 23 days of interest dearer and still fails if buyers pay a week late."""
    calendar = cc.template(24_000_000, 21_000_000)
    options = {
        o.payment_day: o for o in cc.compare_days(calendar, 5_000_000, 19.5, 24, PAYMENT, ISSUE)
    }
    assert all(options[day].base.first_gap is not None for day in (5, 10, 15, 20, 25))
    assert options[28].base.first_gap is None
    assert options[28].delayed.first_gap == date(2026, 11, 28)
    extra = options[28].total_interest - options[5].total_interest
    assert extra == first_period_interest(
        5_000_000, 19.5, ISSUE, date(2026, 11, 28)
    ) - first_period_interest(5_000_000, 19.5, ISSUE, date(2026, 11, 5))

    day, text = cc.recommend(list(options.values()))
    assert day == 28
    assert "задержатся на неделю" in text and "28 ноября" in text


def test_the_demo_story_holds_whatever_the_issue_date() -> None:
    """Client1's template and the pre-approved 5 000 000 ₽ on 24 months, for a year of issue
    dates: days before the 25th receipt open a gap, the 28th does not, a week's delay of
    receipts still does — whenever the jury tries it."""
    calendar = cc.template(24_000_000, 21_000_000)
    for offset in range(0, 366, 5):
        issue = ISSUE + timedelta(days=offset)
        options = {
            o.payment_day: o for o in cc.compare_days(calendar, 5_000_000, 19.5, 24, PAYMENT, issue)
        }
        assert all(options[day].base.first_gap for day in (5, 10, 15, 20, 25)), issue
        assert options[28].base.first_gap is None, issue
        assert options[28].delayed.first_gap is not None, issue
        assert cc.recommend(list(options.values()))[0] == 28, issue


def test_recommendation_when_every_day_fails() -> None:
    calendar = month((10, 100_000), opening=0)
    options = cc.compare_days(calendar, 5_000_000, 19.5, 24, PAYMENT, ISSUE)
    day, text = cc.recommend(options)
    assert day is None and "в любой из дней" in text


# --- API ---------------------------------------------------------------------------


@pytest.fixture
def approved(app: FastAPI, client: TestClient, login_as: LoginAs) -> tuple[str, dict[str, str]]:
    """Client1's application for 5 000 000 ₽ on 24 months, approved by the pipeline."""
    headers = login_as("client1")
    body = {"product_id": "working_capital", "amount": 5_000_000, "term_months": 24}
    app_id = client.post("/api/applications", json=body, headers=headers).json()["id"]
    client.post(
        f"/api/applications/{app_id}/submit", headers=headers | {"Idempotency-Key": str(uuid4())}
    )
    ctx = PipelineContext(FakeIntegrations(), app.state.products)
    run_until_idle(app.state.session_factory, ctx, datetime.now(UTC))
    assert client.get(f"/api/applications/{app_id}", headers=headers).json()["status"] == "approved"
    return app_id, headers


def test_preview_starts_from_a_template_and_recommends_a_day(
    client: TestClient, approved: tuple[str, dict[str, str]]
) -> None:
    app_id, headers = approved
    response = client.post(
        f"/api/applications/{app_id}/cash-calendar/preview", json={}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["template"] is True
    assert body["recommended_day"] == body["payment_day"] == 28
    assert [o["payment_day"] for o in body["options"]] == list(cc.COMPARED_DAYS)
    assert body["options"][0]["extra_cost"] == 0
    assert len(body["chart_base"]) == len(body["chart_delayed"]) > 150

    custom = client.post(
        f"/api/applications/{app_id}/cash-calendar/preview",
        json={"calendar": body["calendar"], "payment_day": 12},
        headers=headers,
    ).json()
    assert custom["template"] is False and custom["payment_day"] == 12
    assert 12 in [o["payment_day"] for o in custom["options"]]


def test_saved_day_dates_the_schedule_for_both_sides(
    client: TestClient, login_as: LoginAs, approved: tuple[str, dict[str, str]]
) -> None:
    app_id, headers = approved
    calendar: dict[str, Any] = client.post(
        f"/api/applications/{app_id}/cash-calendar/preview", json={}, headers=headers
    ).json()["calendar"]
    saved = client.put(
        f"/api/applications/{app_id}/cash-calendar",
        json={"calendar": calendar, "payment_day": 28},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    detail = saved.json()
    schedule = detail["schedule"]
    assert schedule["payment_day"] == 28
    assert schedule["issue_date"] == datetime.now(UTC).date().isoformat()
    assert all(p["due_date"].endswith("-28") for p in schedule["payments"])
    assert detail["cash_plan"]["payment_day"] == 28
    assert detail["cash_plan"]["base"]["first_gap"] is None

    employee = client.get(f"/api/applications/{app_id}", headers=login_as("analyst")).json()
    assert employee["cash_plan"] == detail["cash_plan"]

    # Accepting keeps the day; signing issues the loan and the dates stay.
    client.post(f"/api/applications/{app_id}/accept", json={"accept": True}, headers=headers)
    issued = client.post(f"/api/applications/{app_id}/sign", headers=headers).json()
    assert issued["status"] == "issued"
    assert issued["schedule"]["payment_day"] == 28


@pytest.mark.parametrize(
    "body",
    [
        {"calendar": {"opening_balance": 0, "events": []}, "payment_day": 29},
        {
            "calendar": {"opening_balance": 0, "events": [{"day": 32, "amount": 1}]},
            "payment_day": 5,
        },
        {
            "calendar": {"opening_balance": 0, "events": [{"day": 1, "amount": 1}] * 41},
            "payment_day": 5,
        },
    ],
)
def test_save_validates_input(
    client: TestClient, approved: tuple[str, dict[str, str]], body: dict[str, Any]
) -> None:
    app_id, headers = approved
    assert (
        client.put(
            f"/api/applications/{app_id}/cash-calendar", json=body, headers=headers
        ).status_code
        == 422
    )


def test_only_the_client_and_only_for_an_offer(
    client: TestClient, login_as: LoginAs, approved: tuple[str, dict[str, str]]
) -> None:
    app_id, headers = approved
    url = f"/api/applications/{app_id}/cash-calendar/preview"
    assert client.post(url, json={}, headers=login_as("analyst")).status_code == 403
    draft = client.post(
        "/api/applications",
        json={"product_id": "working_capital", "amount": 1_000_000, "term_months": 12},
        headers=headers,
    ).json()
    response = client.post(
        f"/api/applications/{draft['id']}/cash-calendar/preview", json={}, headers=headers
    )
    assert response.status_code == 409
