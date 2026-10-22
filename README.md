# Умный кредитный кабинет предпринимателя

Веб-прототип кредитного конвейера для малого бизнеса: предприниматель подаёт заявку
и видит её статус, банк проверяет её и принимает решение в том же продукте.

> Черновик README. Полную версию по требованиям кейса (архитектура, сценарий проверки,
> допущения) дописываем к субботе.

## Запуск

Нужны Docker Desktop и GNU Make.

```bash
make up
```

- Приложение: <http://localhost:8080>
- Swagger: <http://localhost:8080/api/docs>

Тестовые учётные записи (логин = пароль): `client1` … `client8`, сотрудник банка `analyst`.
Какой клиент к какому сценарию — в [`docs/scenarios.md`](docs/scenarios.md).

`make down` — остановить, `make reset` — остановить и удалить базу, `make help` — все команды.

## Структура

```
backend/
  app/
    main.py             сборка FastAPI-приложения
    config.py           настройки из переменных окружения
    db.py               подключение к базе и сессия на запрос
    models.py           таблицы базы
    schemas.py          схемы запросов и ответов API
    security.py         пароли, JWT, текущий пользователь
    statuses.py         статусы заявки, переходы, подписи для интерфейса
    credit_decision.py  кредитные правила (чистые функции)
    products.py         чтение config/products.yaml
    seed.py             загрузка демо-данных
    stubs.py            временные заглушки, удаляются по мере готовности API
    routes/             HTTP-эндпоинты
  config/               продукты, пороги, демо-компании
  migrations/           миграции Alembic
  tests/
frontend/               React + TypeScript
nginx/nginx.conf        /api → бэкенд, остальное → фронтенд
docs/                   сценарии и договорённости
```

Правило: новые файлы кладём в `app/` или `app/routes/`, без новых уровней вложенности.

## Разработка

Бэкенд без Docker (нужен запущенный Postgres, например `docker compose up db`):

```bash
cd backend
uv sync --group dev
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:create_app --factory --reload
```

Новая миграция после изменения `app/models.py`:

```bash
uv run alembic revision --autogenerate -m "что изменилось"
```

Фронтенд без Docker:

```bash
cd frontend
npm ci
npm run dev
```

Проверки перед PR — `make test` (то же гоняет CI).

## Кредитные правила (ML Б)

`app.credit_decision.decide(product, request, score, facts, alternatives=())` —
чистая детерминированная функция на стандартных dataclass. Бэкенд загружает
`config/products.yaml` через `load_products` и передаёт `.params` нужного продукта.
Это единый источник параметров для каталога, сида и решения; отдельный
`decision_rules.yaml` не нужен в текущей структуре проекта.

Правила применяются по порядку:

1. Ликвидация, ликвидированная компания или отсутствие в реестре — отказ.
2. `missing_fields` или отсутствующие финансовые показатели — уточнение.
3. Недостаточный возраст бизнеса — другой подходящий продукт либо отказ.
4. PD ≥ `reject_min_pd` — отказ.
5. PD > `approve_max_pd` или сумма > `max_auto_amount` — ручная проверка.
6. Сумма или срок вне диапазона продукта — отказ.
7. Превышение нагрузки — сначала ближайший подходящий более длинный срок,
   затем максимальная доступная сумма в целых рублях на максимальный срок,
   затем другой продукт; если вариантов нет — отказ.
8. Иначе — одобрение. Ставка = `base_rate + risk_premium[risk_class]`.

Нагрузка рассчитывается как `(liabilities_total + monthly_payment * 12) / revenue_year`.
Платёж аннуитетный, округляется до рубля; равенство лимиту допускается.
Нулевая выручка не позволяет выдать кредит. Это упрощённые демонстрационные
правила, пороги согласованы в `docs/scenarios.md`, на реальных данных не обучались.

Каждое решение содержит стабильный `rule`, объяснение `reason`, а одобрение и
встречное предложение — `offer`. Альтернативы проверяются по собственным
порогам и в порядке, заданном вызывающим кодом. Бэкенд должен передавать только
продукты, допустимые для назначения заявки: назначения нет в `LoanRequest`.
Ошибки интеграции (несовпадение продукта, некорректный PD, отрицательные
показатели) вызывают `ValueError`. Недоступность внешнего сервиса и ретраи
обрабатываются бэкендом до вызова функции, как в сценарии 7.

Пример интеграции:

```python
from pathlib import Path
from app.credit_decision import CompanyFacts, LoanRequest, RegistryStatus, ScoreInput, decide
from app.products import load_products

products = load_products(Path("config/products.yaml"))
decision = decide(
    products["working_capital"].params,
    LoanRequest("working_capital", 1_500_000, 12),
    ScoreInput(pd=0.05, risk_class="low", points_total=612),
    CompanyFacts(RegistryStatus.ACTIVE, 36, 24_000_000, 21_000_000, 2_000_000),
)
assert decision.rule == "approved"
```

Проверка: `cd backend && uv run pytest -q tests/test_decision_rules.py tests/test_credit_decision.py`.
HTTP-эндпоинты заявок пока используют заглушки; подключение функции к конвейеру
выполняется отдельно бэкендом.

## Как работаем с Git

- В `main` напрямую не пушим: ветка `feature/<имя>` → pull request → merge после зелёного CI.
- Перед работой — `git pull` свежего `main`.
- Зависимости только через `uv add` / `npm install`, lock-файлы коммитим.
- `.env` и секреты не коммитим; новые переменные — в `.env.example`.
