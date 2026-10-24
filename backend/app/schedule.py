"""Payment schedule for the offered or signed loan terms (annuity, monthly payments).

The regular payment is the one stored with the decision, so the schedule never disagrees
with the offer the client sees. Interest is charged on the remaining debt every month;
the last payment closes the debt exactly and absorbs the rounding to whole rubles.
"""

from dataclasses import dataclass

from app.credit_decision import annuity_payment


@dataclass(frozen=True)
class Payment:
    number: int
    payment: int
    principal: int
    interest: int
    balance: int
    """Debt left after this payment, rubles."""


def annuity_schedule(
    amount: int, annual_rate_percent: float, term_months: int, regular_payment: int | None = None
) -> list[Payment]:
    """Monthly payments in rubles; `regular_payment` defaults to the annuity formula."""
    regular = regular_payment or annuity_payment(amount, annual_rate_percent, term_months)
    monthly_rate = annual_rate_percent / 100 / 12
    balance = amount
    payments: list[Payment] = []
    for number in range(1, term_months + 1):
        interest = round(balance * monthly_rate)
        last = number == term_months
        principal = balance if last else max(0, min(regular - interest, balance))
        balance -= principal
        payments.append(Payment(number, principal + interest, principal, interest, balance))
    return payments
