"""Синтетика для ИНН, которых нет в data/companies.json (сценарий 12: своя компания жюри).

Ответ полностью определяется ИНН: один и тот же ИНН всегда даёт одну и ту же компанию.
ЕГРЮЛ и БКИ отвечают, «Прозрачный бизнес» не знает такие компании (404): финпоказатели
клиент вводит сам. Кредитная история безобидная (без просрочек 30+ дней), чтобы
исход заявки зависел от введённых цифр, а не от случайной просрочки.
"""

import random
from datetime import date, timedelta
from typing import Any

from generate import INITIALS, NAME_SUFFIXES, NAME_WORDS, OKVEDS, REFERENCE_DATE, SURNAMES

VALID_INN_LENGTHS = (10, 12)


def is_valid_inn(inn: str) -> bool:
    return inn.isascii() and inn.isdigit() and len(inn) in VALID_INN_LENGTHS


def synthesize(inn: str) -> dict[str, Any]:
    # строковый seed детерминирован между запусками (в отличие от hash())
    rng = random.Random(f"synthetic:{inn}")
    legal_form = "IP" if len(inn) == 12 else "OOO"
    surname = rng.choice(SURNAMES)
    initials = rng.choice(INITIALS)
    if legal_form == "OOO":
        name = f"ООО «{rng.choice(NAME_WORDS)} {rng.choice(NAME_SUFFIXES)}»"
    else:
        name = f"ИП {surname} {initials}"

    age_months = rng.randint(14, 150)
    registration = REFERENCE_DATE - timedelta(days=round(age_months * 30.44))

    active_loans = rng.randint(0, 2)
    overdue_count = 0
    max_overdue_days = 0
    if rng.random() < 0.15:
        overdue_count = 1
        max_overdue_days = rng.choice([5, 12, 25])

    return {
        "inn": inn,
        "name": name,
        "legal_form": legal_form,
        "okved": rng.choice(OKVEDS),
        "registration_date": _iso(registration),
        "region": inn[:2],
        "status": "active",
        "director": f"{surname} {initials}",
        "financials": None,
        "credit_history": {
            "active_loans": active_loans,
            "overdue_count": overdue_count,
            "max_overdue_days": max_overdue_days,
            "total_debt": active_loans * rng.choice([500_000, 1_000_000, 1_500_000]),
        },
        "demo": None,
    }


def _iso(d: date) -> str:
    return d.isoformat()
