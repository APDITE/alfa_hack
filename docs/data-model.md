# Модель данных

<!-- Сгенерировано `make docs` (backend/app/docgen.py) из кода. Не править вручную. -->

PostgreSQL 16, схема создаётся миграциями Alembic (`backend/migrations`).
Перечисления хранятся строками со значениями из кода (`app/statuses.py`).

```mermaid
erDiagram
    companies {
        string inn PK
        string name
        string legal_form
        string okved
        date registration_date
        string region
        string director
        string registry_status
        timestamptz updated_at
    }
    products {
        string id PK
        string name
        text description
        json purposes
        bigint min_amount
        bigint max_amount
        int min_term_months
        int max_term_months
        float base_rate
        int min_business_age_months
    }
    financial_statements {
        uuid id PK
        string company_inn FK
        date period_end
        bigint revenue_year
        bigint expenses_year
        bigint liabilities_total
        string source
        timestamptz created_at
    }
    users {
        uuid id PK
        string login
        string password_hash
        string full_name
        enum role
        string company_inn FK
        timestamptz created_at
    }
    applications {
        uuid id PK
        uuid client_id FK
        string company_inn FK
        string product_id FK
        string purpose_category
        string purpose
        bigint amount
        int term_months
        bigint revenue_year
        bigint expenses_year
        bigint liabilities_total
        enum status
        bool waiting_external
        string idempotency_key
        timestamptz created_at
        timestamptz updated_at
        timestamptz submitted_at
        int payment_day
        json cash_calendar
    }
    agreements {
        uuid id PK
        uuid application_id FK
        int version
        int offer_version
        string number
        string reason
        text text
        string sha256
        timestamptz created_at
        timestamptz signed_at
    }
    check_results {
        uuid id PK
        uuid application_id FK
        string type
        string outcome
        text summary
        json payload
        int attempt
        timestamptz created_at
    }
    clarifications {
        uuid id PK
        uuid application_id FK
        json requested_fields
        text message
        enum requested_by
        text answer
        timestamptz created_at
        timestamptz answered_at
    }
    decisions {
        uuid id PK
        uuid application_id FK
        string outcome
        string rule
        text reason
        json offer
        enum decided_by
        uuid decided_by_user_id FK
        text comment
        timestamptz created_at
    }
    feed_items {
        uuid id PK
        uuid user_id FK
        uuid application_id FK
        string type
        string title
        text text
        bool read
        timestamptz created_at
    }
    pipeline_jobs {
        uuid id PK
        uuid application_id FK
        enum stage
        enum status
        int attempt
        timestamptz run_after
        text last_error
        timestamptz created_at
        timestamptz updated_at
    }
    proposals {
        uuid id PK
        uuid application_id FK
        int round
        int offer_version
        bigint amount
        int term_months
        float rate
        text comment
        uuid created_by_user_id FK
        timestamptz created_at
        timestamptz answered_at
        int answer_version
    }
    score_results {
        uuid id PK
        uuid application_id FK
        float pd
        string risk_class
        int points_total
        json factors
        string model_version
        timestamptz created_at
    }
    status_history {
        uuid id PK
        uuid application_id FK
        enum from_status
        enum to_status
        enum actor
        uuid actor_user_id FK
        text comment
        timestamptz created_at
    }
    financial_statements }o--|| companies : "company_inn"
    users }o--o| companies : "company_inn"
    applications }o--|| users : "client_id"
    applications }o--|| companies : "company_inn"
    applications }o--|| products : "product_id"
    agreements }o--|| applications : "application_id"
    check_results }o--|| applications : "application_id"
    clarifications }o--|| applications : "application_id"
    decisions }o--|| applications : "application_id"
    decisions }o--o| users : "decided_by_user_id"
    feed_items }o--|| users : "user_id"
    feed_items }o--o| applications : "application_id"
    pipeline_jobs }o--|| applications : "application_id"
    proposals }o--|| applications : "application_id"
    proposals }o--o| users : "created_by_user_id"
    score_results }o--|| applications : "application_id"
    status_history }o--|| applications : "application_id"
    status_history }o--o| users : "actor_user_id"
```

| Таблица | Назначение |
| --- | --- |
| `companies` | Компании клиентов: реквизиты из реестра (сид из `config/demo_companies.yaml`). |
| `products` | Кредитные продукты (сид из `config/products.yaml`). |
| `financial_statements` | Зарезервирована под историю отчётности; в текущей версии не заполняется. |
| `users` | Учётные записи клиентов и сотрудников банка; пароли хранятся в bcrypt. |
| `applications` | Заявка: продукт, сумма, срок, цель, финпоказатели клиента, статус, ключ идемпотентности. |
| `agreements` |  |
| `check_results` | Результаты проверок: полнота, ЕГРЮЛ/ЕГРИП, «Прозрачный бизнес», БКИ — с исходным ответом источника. |
| `clarifications` | Запросы уточнений (системы или сотрудника) и ответы клиента. |
| `decisions` | Решения системы и сотрудника: правило, объяснение для клиента, условия. |
| `feed_items` | Уведомления клиента о ходе заявки; создаются при переходах статуса. |
| `pipeline_jobs` | Очередь задач конвейера: этап, попытка, время следующего запуска (`SELECT … FOR UPDATE SKIP LOCKED`). |
| `proposals` |  |
| `score_results` | Оценка риска: PD, класс риска, баллы, факторы, версия модели. |
| `status_history` | Журнал переходов: откуда, куда, кто (клиент, система, сотрудник), комментарий. Это аудит заявки. |
