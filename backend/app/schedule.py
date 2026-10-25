"""Payment schedule for the offered or signed loan terms (annuity, monthly payments).

The regular payment is the one stored with the decision, so the schedule never disagrees
with the offer the client sees. Interest is charged on the remaining debt every month;
the last payment closes the debt exactly and absorbs the rounding to whole rubles.

Once the client has chosen a payment day (the cash calendar), payments get dates: the
chosen day of every month, starting with the month after the issue. The first period
then runs from the issue to the first payment, and its interest is charged by days
(ACT/365): a later payment day makes the first payment, and the loan, more expensive.
"""

import calendar
from dataclasses import dataclass
from datetime import date

from app.credit_decision import annuity_payment

MAX_PAYMENT_DAY = 28
"""Payment days run 1–28, so that every month has the chosen day."""


@dataclass(frozen=True)
class Payment:
    number: int
    payment: int
    principal: int
    interest: int
    balance: int
    """Debt left after this payment, rubles."""
    due_date: date | None = None


def payment_dates(issue: date, payment_day: int, term_months: int) -> list[date]:
    """The payment day of every month, starting with the month after the issue."""
    if not 1 <= payment_day <= MAX_PAYMENT_DAY:
        raise ValueError(f"payment_day must be between 1 and {MAX_PAYMENT_DAY}")
    dates: list[date] = []
    year, month = issue.year, issue.month
    for _ in range(term_months):
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        dates.append(date(year, month, min(payment_day, calendar.monthrange(year, month)[1])))
    return dates


def first_period_interest(amount: int, annual_rate_percent: float, issue: date, first: date) -> int:
    """Interest from the issue to the first payment, by days (ACT/365)."""
    return round(amount * annual_rate_percent / 100 * (first - issue).days / 365)


def annuity_schedule(
    amount: int,
    annual_rate_percent: float,
    term_months: int,
    regular_payment: int | None = None,
    issue: date | None = None,
    payment_day: int | None = None,
) -> list[Payment]:
    """Monthly payments in rubles; `regular_payment` defaults to the annuity formula.

    With `issue` and `payment_day` the payments are dated and the first interest is
    charged by days; the debt is repaid along the same path either way.
    """
    regular = regular_payment or annuity_payment(amount, annual_rate_percent, term_months)
    monthly_rate = annual_rate_percent / 100 / 12
    dates = (
        payment_dates(issue, payment_day, term_months)
        if issue is not None and payment_day is not None
        else None
    )
    balance = amount
    payments: list[Payment] = []
    for number in range(1, term_months + 1):
        interest = round(balance * monthly_rate)
        last = number == term_months
        principal = balance if last else max(0, min(regular - interest, balance))
        if dates is not None and number == 1 and issue is not None:
            interest = first_period_interest(balance, annual_rate_percent, issue, dates[0])
        balance -= principal
        due = dates[number - 1] if dates is not None else None
        payments.append(Payment(number, principal + interest, principal, interest, balance, due))
    return payments
