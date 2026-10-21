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

## Как работаем с Git

- В `main` напрямую не пушим: ветка `feature/<имя>` → pull request → merge после зелёного CI.
- Перед работой — `git pull` свежего `main`.
- Зависимости только через `uv add` / `npm install`, lock-файлы коммитим.
- `.env` и секреты не коммитим; новые переменные — в `.env.example`.
