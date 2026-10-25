"""Cash calendar: does the loan payment fit the company's own cash flow?

The client describes a typical month: receipts and payments by day of month, and the
balance on the account at the start of the month of the first loan payment. For a payment
day the module walks day by day through the whole loan term and finds the lowest balance
and the first cash gap — the balance falling below the reserve the client wants to keep.
Within a day, payments go out before receipts come in: money that arrives in the evening
cannot pay a bill due in the morning.

The stress scenario delays every receipt by a week. A later payment day costs money: the
first interest period gets longer (`schedule.first_period_interest`), so every compared day
is priced too. Loan proceeds are not added to the balance: they are spent on the purpose of
the loan. The credit decision does not use the calendar; it helps the client pick the
payment day and shows the employee the risk.

Pure module: no database, no HTTP.
"""

import calendar as cal
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.schedule import annuity_schedule

DELAY_DAYS = 7
COMPARED_DAYS = (5, 10, 15, 20, 25, 28)

_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


@dataclass(frozen=True)
class CashEvent:
    day: int
    """Day of month, 1–31; a day the month does not have means its last day."""
    amount: int
    """Rubles: positive — a receipt, negative — a payment."""
    label: str = ""


@dataclass(frozen=True)
class CashCalendar:
    opening_balance: int
    """Balance at the start of the month of the first loan payment, rubles."""
    reserve: int
    """Balance the company wants to keep; going below it is a cash gap."""
    events: tuple[CashEvent, ...]


@dataclass(frozen=True)
class Simulation:
    min_balance: int
    min_date: date
    first_gap: date | None
    shortfall: int
    """Missing below the reserve at the worst moment, rubles; 0 — no gap."""
    lows: list[tuple[date, int]]
    """The lowest balance of every day, for the chart."""


@dataclass(frozen=True)
class DayOption:
    payment_day: int
    first_payment_date: date
    first_payment: int
    total_interest: int
    base: Simulation
    delayed: Simulation


def simulate(
    calendar: CashCalendar, payments: list[tuple[date, int]], delay_days: int = 0
) -> Simulation:
    """Day by day from the 1st of the first payment month to the last payment."""
    start = payments[0][0].replace(day=1)
    end = payments[-1][0]
    outflows: dict[date, int] = defaultdict(int)
    inflows: dict[date, int] = defaultdict(int)
    for due, amount in payments:
        outflows[due] += amount
    year, month = start.year, start.month
    while date(year, month, 1) <= end:
        last = cal.monthrange(year, month)[1]
        for event in calendar.events:
            when = date(year, month, min(event.day, last))
            if event.amount < 0:
                outflows[when] -= event.amount
            else:
                inflows[when + timedelta(days=delay_days)] += event.amount
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    balance = calendar.opening_balance
    lows: list[tuple[date, int]] = []
    min_balance, min_date = balance, start
    first_gap: date | None = None
    day = start
    while day <= end:
        balance -= outflows.get(day, 0)
        lows.append((day, balance))
        if balance < min_balance:
            min_balance, min_date = balance, day
        if first_gap is None and balance < calendar.reserve:
            first_gap = day
        balance += inflows.get(day, 0)
        day += timedelta(days=1)
    shortfall = max(0, calendar.reserve - min_balance)
    return Simulation(min_balance, min_date, first_gap, shortfall, lows)


def compare_days(
    calendar: CashCalendar,
    amount: int,
    rate: float,
    term_months: int,
    regular_payment: int,
    issue: date,
    days: tuple[int, ...] = COMPARED_DAYS,
) -> list[DayOption]:
    """Every payment day priced and checked against the cash flow, as is and delayed."""
    options: list[DayOption] = []
    for payment_day in days:
        schedule = annuity_schedule(amount, rate, term_months, regular_payment, issue, payment_day)
        payments = [(p.due_date, p.payment) for p in schedule if p.due_date is not None]
        options.append(
            DayOption(
                payment_day=payment_day,
                first_payment_date=payments[0][0],
                first_payment=schedule[0].payment,
                total_interest=sum(p.interest for p in schedule),
                base=simulate(calendar, payments),
                delayed=simulate(calendar, payments, DELAY_DAYS),
            )
        )
    return options


def recommend(options: list[DayOption]) -> tuple[int | None, str]:
    """The payment day to suggest and why, in plain language.

    No gap as planned comes first, then no gap with receipts a week late, then the price.
    """
    safe = [o for o in options if o.base.first_gap is None]
    if not safe:
        best = min(options, key=lambda o: o.base.shortfall)
        return None, (
            "При таких поступлениях платёж в любой из дней создаёт кассовый разрыв. "
            f"Меньше всего он при платеже {best.payment_day}-го числа — до "
            f"{money(best.base.shortfall)}. Уменьшите сумму, увеличьте срок или проверьте "
            "остаток и даты поступлений."
        )
    robust = [o for o in safe if o.delayed.first_gap is None]
    if robust:
        best = min(robust, key=lambda o: o.total_interest)
        return best.payment_day, (
            f"Платёж {best.payment_day}-го числа: кассового разрыва нет, и задержку "
            "поступлений на неделю бизнес тоже выдерживает."
        )
    best = min(safe, key=lambda o: o.total_interest)
    gap = best.delayed
    assert gap.first_gap is not None
    starts = day_month(gap.first_gap)
    if gap.first_gap.year != best.first_payment_date.year:
        starts += f" {gap.first_gap.year} года"
    return best.payment_day, (
        f"Платёж {best.payment_day}-го числа: кассового разрыва нет. Если поступления "
        f"задержатся на неделю, разрыв начнётся {starts} и в худший момент "
        f"составит {money(gap.shortfall)} — стоит держать такой резерв на счёте."
    )


def template(revenue_year: int | None, expenses_year: int | None) -> CashCalendar:
    """A starting point from the yearly figures; the client corrects days and amounts.

    Salaries and taxes on the 5th, suppliers and rent on the 20th, buyers pay half of the
    monthly revenue on the 10th and half on the 25th; half a month of revenue is on the
    account at the start of the month.
    """
    revenue = (revenue_year or 0) / 12
    expenses = (expenses_year or 0) / 12
    events = (
        CashEvent(5, -_round(expenses * 0.4, 1_000), "Зарплата и налоги"),
        CashEvent(10, _round(revenue / 2, 1_000), "Оплата от покупателей"),
        CashEvent(20, -_round(expenses * 0.6, 1_000), "Поставщики и аренда"),
        CashEvent(25, _round(revenue / 2, 1_000), "Оплата от покупателей"),
    )
    return CashCalendar(
        opening_balance=_round(revenue / 2, 10_000),
        reserve=0,
        events=tuple(e for e in events if e.amount != 0),
    )


def money(value: int) -> str:
    return f"{value:,} ₽".replace(",", " ")


def day_month(value: date) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]}"


def _round(value: float, step: int) -> int:
    return int(round(value / step)) * step
