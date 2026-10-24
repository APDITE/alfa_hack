"""Generate docs from the code: `python -m app.docgen [out_dir]` (default: ../docs).

- state-diagram.md: Mermaid state diagram and the status table, from app/statuses.py
- data-model.md: Mermaid ER diagram, from the SQLAlchemy models
- openapi.json: the API contract, as served at /api/openapi.json

tests/test_docs.py checks that docs/state-diagram.md matches the code.
"""

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.types import TypeEngine

from app import models as _models  # noqa: F401  (registers the tables)
from app.config import Settings
from app.db import Base
from app.main import create_app
from app.statuses import (
    CLIENT_STAGE,
    FINAL_STATUSES,
    NEXT_STEPS,
    STAGE_LABELS,
    STATUS_LABELS,
    TRANSITIONS,
    TURN_OWNER,
    Actor,
    ApplicationStatus,
)

_GENERATED = (
    "<!-- Сгенерировано `make docs` (backend/app/docgen.py) из кода. Не править вручную. -->"
)

_ACTOR = {Actor.CLIENT: "клиент", Actor.SYSTEM: "система", Actor.EMPLOYEE: "сотрудник"}


def state_diagram() -> str:
    lines = [
        "# Диаграмма состояний заявки",
        "",
        _GENERATED,
        "",
        "Источник — `backend/app/statuses.py`: таблица переходов `TRANSITIONS` и владелец хода",
        "`TURN_OWNER`. Подпись на стрелке — кто переводит заявку из исходного статуса. Любой",
        "переход проходит через `lifecycle.transition`: недопустимый переход или чужой ход",
        "отклоняется (HTTP 409), каждый переход пишется в `status_history`.",
        "",
        "```mermaid",
        "stateDiagram-v2",
    ]
    for status in ApplicationStatus:
        lines.append(f'    state "{STATUS_LABELS[status]}" as {status.value}')
    lines.append(f"    [*] --> {ApplicationStatus.DRAFT.value}")
    for source in ApplicationStatus:
        owner = TURN_OWNER[source]
        for target in sorted(TRANSITIONS[source]):
            label = _ACTOR[owner] if owner is not None else ""
            lines.append(f"    {source.value} --> {target.value} : {label}")
    for status in sorted(FINAL_STATUSES):
        lines.append(f"    {status.value} --> [*]")
    lines += [
        "```",
        "",
        "| Статус | Подпись | Этап для клиента | Чей ход | Следующие статусы | Что видит клиент |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for status in ApplicationStatus:
        owner = TURN_OWNER[status]
        targets = ", ".join(f"`{t.value}`" for t in sorted(TRANSITIONS[status])) or "—"
        lines.append(
            f"| `{status.value}` | {STATUS_LABELS[status]} | {STAGE_LABELS[CLIENT_STAGE[status]]} "
            f"| {_ACTOR[owner] if owner else '—'} | {targets} | {NEXT_STEPS[status]} |"
        )
    return "\n".join(lines) + "\n"


_TYPES: list[tuple[type[TypeEngine[Any]], str]] = [
    (Uuid, "uuid"),
    (BigInteger, "bigint"),
    (Integer, "int"),
    (Float, "float"),
    (Boolean, "bool"),
    (DateTime, "timestamptz"),
    (Date, "date"),
    (JSON, "json"),
    (Enum, "enum"),
    (Text, "text"),
    (String, "string"),
]

_TABLES = {
    "users": "Учётные записи клиентов и сотрудников банка; пароли хранятся в bcrypt.",
    "companies": "Компании клиентов: реквизиты из реестра (сид из `config/demo_companies.yaml`).",
    "financial_statements": "Зарезервирована под историю отчётности; "
    "в текущей версии не заполняется.",
    "products": "Кредитные продукты (сид из `config/products.yaml`).",
    "applications": "Заявка: продукт, сумма, срок, цель, финпоказатели клиента, статус, "
    "ключ идемпотентности.",
    "status_history": "Журнал переходов: откуда, куда, кто (клиент, система, сотрудник), "
    "комментарий. Это аудит заявки.",
    "clarifications": "Запросы уточнений (системы или сотрудника) и ответы клиента.",
    "check_results": "Результаты проверок: полнота, ЕГРЮЛ/ЕГРИП, «Прозрачный бизнес», БКИ — "
    "с исходным ответом источника.",
    "score_results": "Оценка риска: PD, класс риска, баллы, факторы, версия модели.",
    "decisions": "Решения системы и сотрудника: правило, объяснение для клиента, условия.",
    "pipeline_jobs": "Очередь задач конвейера: этап, попытка, время следующего запуска "
    "(`SELECT … FOR UPDATE SKIP LOCKED`).",
    "feed_items": "Уведомления клиента о ходе заявки; создаются при переходах статуса.",
}


def _type_name(column_type: TypeEngine[Any]) -> str:
    for sa_type, name in _TYPES:
        if isinstance(column_type, sa_type):
            return name
    return type(column_type).__name__.lower()


def data_model() -> str:
    lines = [
        "# Модель данных",
        "",
        _GENERATED,
        "",
        "PostgreSQL 16, схема создаётся миграциями Alembic (`backend/migrations`).",
        "Перечисления хранятся строками со значениями из кода (`app/statuses.py`).",
        "",
        "```mermaid",
        "erDiagram",
    ]
    tables = Base.metadata.sorted_tables
    for table in tables:
        lines.append(f"    {table.name} {{")
        for column in table.columns:
            keys = [k for k, on in (("PK", column.primary_key), ("FK", column.foreign_keys)) if on]
            suffix = f" {', '.join(keys)}" if keys else ""
            lines.append(f"        {_type_name(column.type)} {column.name}{suffix}")
        lines.append("    }")
    for table in tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                cardinality = "}o--o|" if column.nullable else "}o--||"
                lines.append(f'    {table.name} {cardinality} {parent} : "{column.name}"')
    lines += ["```", "", "| Таблица | Назначение |", "| --- | --- |"]
    for table in tables:
        lines.append(f"| `{table.name}` | {_TABLES.get(table.name, '')} |")
    return "\n".join(lines) + "\n"


def openapi() -> str:
    app = create_app(Settings(app_env="development", database_url="sqlite+pysqlite:///:memory:"))
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("..") / "docs"
    out.mkdir(parents=True, exist_ok=True)
    for name, content in (
        ("state-diagram.md", state_diagram()),
        ("data-model.md", data_model()),
        ("openapi.json", openapi()),
    ):
        (out / name).write_text(content, encoding="utf-8")
        print(f"wrote {out / name}")


if __name__ == "__main__":
    main()
