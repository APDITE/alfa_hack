"""Генератор синтетических компаний для моков и сида бэкенда.

Запуск:  uv run python generate.py [--out data/companies.json]

Результат полностью определяется SEED и REFERENCE_DATE: два запуска дают
побайтово одинаковый файл. Реальных данных здесь нет, все названия,
ИНН и показатели выдуманы.

Закономерности (чем хуже "качество" компании, тем хуже её показатели)
заданы нами вручную: настоящих меток "вернул или не вернул" у нас нет.
"""

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SEED = 20261020
# фиксированная "сегодняшняя" дата: возраст компаний не зависит от дня запуска
REFERENCE_DATE = date(2026, 10, 21)
BACKGROUND_COUNT = 180

DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "companies.json"

REGIONS = ["77", "78", "50", "16", "66", "54", "23", "52", "63", "74"]
OKVEDS = ["47.11", "49.41", "56.10", "41.20", "43.21", "10.71", "62.01", "68.20", "01.11", "46.90", "25.62", "96.02"]
NAME_WORDS = [
    "Альтаир", "Меридиан", "Северный", "Горизонт", "Гранит", "Импульс", "Каскад", "Лотос",
    "Маяк", "Навигатор", "Орбита", "Прогресс", "Рассвет", "Сигма", "Титан", "Урал",
    "Фаворит", "Холдинг", "Цитадель", "Эталон", "Юпитер", "Янтарь", "Бриз", "Вега",
]
NAME_SUFFIXES = ["Трейд", "Сервис", "Групп", "Строй", "Лого", "Продукт", "Техно", "Опт", "Плюс", "Эко"]
SURNAMES = [
    "Иванов", "Петров", "Сидоров", "Кузнецов", "Смирнов", "Попов", "Васильев", "Соколов",
    "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов",
]
INITIALS = ["А. А.", "Б. В.", "В. И.", "Г. Д.", "Д. С.", "Е. П.", "И. И.", "К. Н.", "М. А.", "О. В.", "С. Л.", "Т. Р."]


def _registration_date(age_months: int) -> str:
    return (REFERENCE_DATE - timedelta(days=round(age_months * 30.44))).isoformat()


def _company(
    *,
    inn: str,
    name: str,
    okved: str,
    age_months: int | None = None,
    registration_date: str | None = None,
    revenue: int,
    expenses: int,
    liabilities: int,
    employees: int,
    tax_arrears: bool,
    active_loans: int,
    overdue_count: int,
    max_overdue_days: int,
    total_debt: int,
    director: str,
    status: str = "active",
    region: str = "77",
    legal_form: str = "OOO",
    financials: bool = True,
    credit_history: bool = True,
    demo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if registration_date is None:
        assert age_months is not None, "pass registration_date or age_months"
        registration_date = _registration_date(age_months)
    return {
        "inn": inn,
        "name": name,
        "legal_form": legal_form,
        "okved": okved,
        "registration_date": registration_date,
        "region": region,
        "status": status,
        "director": director,
        "financials": {
            "revenue_year": revenue,
            "expenses_year": expenses,
            "liabilities_total": liabilities,
            "employees": employees,
            "tax_arrears": tax_arrears,
        }
        if financials
        else None,
        "credit_history": {
            "active_loans": active_loans,
            "overdue_count": overdue_count,
            "max_overdue_days": max_overdue_days,
            "total_debt": total_debt,
        }
        if credit_history
        else None,
        "demo": demo,
    }


def _demo(scenarios: list[int], title: str, expected: str, *requests: tuple[str, int, int]) -> dict[str, Any]:
    return {
        "scenarios": scenarios,
        "title": title,
        "expected": expected,
        "suggested_applications": [
            {"product_id": p, "amount": a, "term_months": t} for p, a, t in requests
        ],
    }


def demo_companies() -> list[dict[str, Any]]:
    """Восемь компаний под сценарии из docs/scenarios.md, ИНН 7700000001..7700000008.

    Реквизиты (название, дата регистрации, регион, директор) совпадают с
    backend/config/demo_companies.yaml, номера сценариев с docs/scenarios.md.
    """
    return [
        _company(
            inn="7700000001", name="ООО «Северный ветер»", legal_form="OOO", okved="47.11",
            registration_date="2019-03-15", region="77", director="Смирнова Анна Викторовна",
            revenue=24_000_000, expenses=21_000_000, liabilities=2_000_000, employees=12,
            tax_arrears=False, active_loans=1, overdue_count=0, max_overdue_days=0, total_debt=1_500_000,
            demo=_demo([1, 7], "Сильная компания", "автоодобрение; в сценарии 7 перед заявкой выключить БКИ",
                       ("working_capital", 1_500_000, 12)),
        ),
        _company(
            inn="7700000002", name="ООО «Пекарня на углу»", legal_form="OOO", okved="10.71",
            registration_date="2020-06-01", region="77", director="Орлов Дмитрий Сергеевич",
            revenue=12_000_000, expenses=9_600_000, liabilities=5_000_000, employees=9,
            tax_arrears=False, active_loans=1, overdue_count=0, max_overdue_days=0, total_debt=1_200_000,
            demo=_demo([2], "Пограничная: высокая долговая нагрузка при хорошем риске",
                       "другие условия: длиннее срок или меньше сумма",
                       ("working_capital", 4_000_000, 6)),
        ),
        _company(
            inn="7700000003", name="ИП Ковалёва Мария Игоревна", legal_form="IP", okved="96.02",
            registration_date="2021-09-10", region="50", director="Ковалёва Мария Игоревна",
            revenue=0, expenses=0, liabilities=0, employees=0, financials=False,
            tax_arrears=False, active_loans=0, overdue_count=0, max_overdue_days=0, total_debt=0,
            demo=_demo([3], "Неполные данные",
                       "«Прозрачный бизнес» отвечает 404: запрос уточнения, после ответа клиента автоодобрение",
                       ("working_capital", 800_000, 12)),
        ),
        _company(
            inn="7700000004", name="ООО «СтройМонтаж»", legal_form="OOO", okved="43.21",
            registration_date="2018-02-20", region="77", director="Белов Игорь Петрович",
            revenue=30_000_000, expenses=28_500_000, liabilities=14_000_000, employees=40,
            tax_arrears=True, active_loans=4, overdue_count=4, max_overdue_days=120, total_debt=10_000_000,
            demo=_demo([4], "Просрочка 120 дней и высокая нагрузка", "отказ с понятной причиной",
                       ("working_capital", 3_000_000, 12)),
        ),
        _company(
            inn="7700000005", name="ООО «Агротех»", legal_form="OOO", okved="01.11",
            registration_date="2017-04-05", region="36", director="Никитин Сергей Олегович",
            revenue=15_000_000, expenses=14_700_000, liabilities=6_000_000, employees=18,
            tax_arrears=False, active_loans=3, overdue_count=0, max_overdue_days=0, total_debt=2_400_000,
            demo=_demo([5], "Нестандартный случай: низкая рентабельность, три кредита",
                       "серая зона PD, ручная проверка и решение сотрудника",
                       ("working_capital", 2_000_000, 12)),
        ),
        _company(
            inn="7700000006", name="ООО «Вектор»", legal_form="OOO", okved="46.90",
            registration_date="2016-11-11", region="78", director="Морозов Алексей Иванович",
            status="liquidating",
            revenue=36_000_000, expenses=31_000_000, liabilities=4_000_000, employees=22,
            tax_arrears=False, active_loans=1, overdue_count=0, max_overdue_days=0, total_debt=1_200_000,
            demo=_demo([6], "Компания в стадии ликвидации", "отказ по статусу в ЕГРЮЛ",
                       ("working_capital", 2_000_000, 12)),
        ),
        _company(
            inn="7700000007", name="ООО «Кофейня Зерно»", legal_form="OOO", okved="56.10",
            registration_date="2020-01-20", region="77", director="Лебедева Ольга Андреевна",
            revenue=18_000_000, expenses=16_000_000, liabilities=6_000_000, employees=11,
            tax_arrears=False, active_loans=2, overdue_count=0, max_overdue_days=0, total_debt=2_500_000,
            demo=_demo([8], "Один скоринг, два продукта",
                       "оборотный: автоодобрение, оборудование: ручная проверка",
                       ("working_capital", 2_000_000, 24), ("equipment", 2_000_000, 24)),
        ),
        _company(
            inn="7700000008", name="ИП Захаров Павел Николаевич", legal_form="IP", okved="49.41",
            registration_date="2026-02-01", region="52", director="Захаров Павел Николаевич",
            revenue=21_000_000, expenses=18_000_000, liabilities=3_000_000, employees=6,
            tax_arrears=False, active_loans=0, overdue_count=0, max_overdue_days=0, total_debt=0,
            demo=_demo([11], "Молодой бизнес: восемь месяцев",
                       "другие условия: вместо оборудования предлагается оборотный кредит",
                       ("equipment", 2_000_000, 24)),
        ),
    ]


def _inn(rng: random.Random, legal_form: str, used: set[str]) -> str:
    length = 10 if legal_form == "OOO" else 12
    while True:
        region = rng.choice(REGIONS)
        inn = region + "".join(rng.choice("0123456789") for _ in range(length - 2))
        # не пересекаемся с демо-диапазоном 77000000xx
        if inn not in used and not inn.startswith("77000000"):
            used.add(inn)
            return inn


def background_companies(rng: random.Random, count: int, used: set[str]) -> list[dict[str, Any]]:
    companies = []
    for _ in range(count):
        legal_form = "OOO" if rng.random() < 0.85 else "IP"
        inn = _inn(rng, legal_form, used)
        quality = rng.betavariate(3, 2)  # 0 плохо, 1 отлично

        surname = rng.choice(SURNAMES)
        director = f"{surname} {rng.choice(INITIALS)}"
        if legal_form == "OOO":
            name = f"ООО «{rng.choice(NAME_WORDS)} {rng.choice(NAME_SUFFIXES)}»"
        else:
            name = f"ИП {surname}{'а' if rng.random() < 0.4 else ''} {rng.choice(INITIALS)}"

        age_months = int(rng.triangular(3, 180, 60))
        scale = 4_000_000 if legal_form == "IP" else 15_000_000
        revenue = int(round(scale * rng.lognormvariate(0.6, 0.8), -4))
        margin = -0.05 + 0.25 * quality + rng.gauss(0, 0.03)
        expenses = int(round(revenue * (1 - margin), -4))
        liabilities = int(round(revenue * (1 - quality) * rng.uniform(0.2, 1.0), -4))
        employees = max(1, int(revenue / 2_500_000 * rng.uniform(0.6, 1.4)))
        tax_arrears = rng.random() < 0.02 + 0.2 * (1 - quality) ** 3

        active_loans = min(5, int(rng.expovariate(1.0) * (1.5 - quality)))
        overdue_count = 0
        max_overdue_days = 0
        if rng.random() < 0.9 * (1 - quality) ** 2:
            overdue_count = rng.randint(1, 6)
            max_overdue_days = rng.choice([5, 12, 25, 45, 75, 100, 140])
        total_debt = int(round(liabilities * rng.uniform(0.3, 0.8), -4)) if active_loans else 0

        roll = rng.random()
        status = "active" if roll < 0.94 else ("liquidating" if roll < 0.98 else "liquidated")

        companies.append(
            _company(
                inn=inn, name=name, okved=rng.choice(OKVEDS), age_months=age_months,
                revenue=revenue, expenses=expenses, liabilities=liabilities, employees=employees,
                tax_arrears=tax_arrears, active_loans=active_loans, overdue_count=overdue_count,
                max_overdue_days=max_overdue_days, total_debt=total_debt, director=director,
                status=status, region=inn[:2], legal_form=legal_form,
                # у небольшой доли компаний нет записи в источнике (мок отвечает 404)
                financials=rng.random() >= 0.04,
                credit_history=rng.random() >= 0.03,
            )
        )
    return companies


def generate(seed: int = SEED, background: int = BACKGROUND_COUNT) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    demos = demo_companies()
    used = {c["inn"] for c in demos}
    return demos + background_companies(rng, background, used)


def render(companies: list[dict[str, Any]]) -> str:
    return json.dumps(companies, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    companies = generate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(render(companies))
    print(f"wrote {len(companies)} companies to {args.out}")


if __name__ == "__main__":
    main()
