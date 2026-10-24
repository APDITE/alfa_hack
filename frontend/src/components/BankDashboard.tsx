
import { useCallback, useEffect, useState } from "react";
import {
  getApplications,
  getApplication,
  makeManualDecision,
  type ApplicationSummary,
  type ApplicationDetail,
  type ManualDecisionOutcome,
} from "../api/applications";

type Filter =
  | "all"
  | "new"
  | "review"
  | "approved"
  | "rejected"
  | "clarification";

type ScoreFactor = {
  name: string;
  points: number;
  impact: "increases_risk" | "decreases_risk";
  comment: string;
};

type ScoreView = {
  score: number;
  risk_class: "low" | "medium" | "high";
  points_total: number;
  factors: ScoreFactor[];
  model_version: string;
};

type CheckResult = {
  type: string;
  outcome: string;
  summary: string;
  attempt: number;
};

type BankApplicationDetail = ApplicationDetail & {
  score: ScoreView | null;
  checks: CheckResult[];
  decision: {
    outcome: string;
    reason: string;
    rule: string;
    comment: string | null;
  } | null;
};

const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "new", label: "Новые" },
  { value: "review", label: "На рассмотрении" },
  { value: "approved", label: "Одобрены" },
  { value: "rejected", label: "Отклонены" },
  { value: "clarification", label: "Требуют уточнения" },
];

const riskLabels = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
};

const clarificationFields = [
  { value: "revenue_year", label: "Выручка за год" },
  { value: "expenses_year", label: "Расходы за год" },
  { value: "liabilities_total", label: "Общая задолженность" },
];

function productName(productId: string): string {
  return productId === "working_capital"
    ? "Оборотный кредит"
    : "Кредит на оборудование";
}

function formatAmount(amount: number | null): string {
  return amount === null
    ? "Не указана"
    : `${amount.toLocaleString("ru-RU")} ₽`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Произошла неизвестная ошибка.";
}

export default function BankDashboard() {
  const [applications, setApplications] =
    useState<ApplicationSummary[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedApplication, setSelectedApplication] =
    useState<BankApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [commentInput, setCommentInput] = useState("");
  const [requestedFields, setRequestedFields] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadApplications = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const items = await getApplications();
      setApplications(items);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadApplications();
  }, [loadApplications]);

  async function openApplication(id: string) {
    setDetailsLoading(true);
    setError("");
    setSuccess("");

    try {
      const detail = await getApplication(id);

      setSelectedApplication(detail as BankApplicationDetail);
      setCommentInput("");
      setRequestedFields([]);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setDetailsLoading(false);
    }
  }

  function toggleRequestedField(field: string) {
    setRequestedFields((current) =>
      current.includes(field)
        ? current.filter((item) => item !== field)
        : [...current, field]
    );
  }

  async function decide(outcome: ManualDecisionOutcome) {
    if (!selectedApplication || decisionLoading) return;

    const comment = commentInput.trim();

    if (!comment) {
      setError("Напишите комментарий к решению.");
      return;
    }

    if (outcome === "clarification" && requestedFields.length === 0) {
      setError("Выберите хотя бы одно поле для уточнения.");
      return;
    }

    if (!selectedApplication.available_actions.includes("decide")) {
      setError("Принятие решения по этой заявке недоступно.");
      return;
    }

    const confirmation = {
      approved: "Одобрить заявку?",
      rejected: "Отклонить заявку?",
      clarification: "Отправить запрос на уточнение предпринимателю?",
    }[outcome];

    if (!window.confirm(confirmation)) return;

    setDecisionLoading(true);
    setError("");
    setSuccess("");

    try {
      const updated = await makeManualDecision(
        selectedApplication.id,
        {
          outcome,
          comment,
          ...(outcome === "clarification"
            ? { requested_fields: requestedFields }
            : {}),
        }
      );

      setSelectedApplication(updated as BankApplicationDetail);
      setCommentInput("");
      setRequestedFields([]);
      setSuccess("Решение успешно сохранено в системе банка.");

      const items = await getApplications();
      setApplications(items);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setDecisionLoading(false);
    }
  }

  const filteredApplications = applications.filter((application) => {
    if (filter === "all") return true;

    if (filter === "new") {
      return application.status === "submitted";
    }

    if (filter === "review") {
      return ![
        "draft",
        "submitted",
        "approved",
        "rejected",
        "clarification",
      ].includes(application.status);
    }

    return application.status === filter;
  });

  if (selectedApplication) {
    const application = selectedApplication;
    const canDecide = application.available_actions.includes("decide");

    return (
      <section className="bank-dashboard">
        <button
          type="button"
          className="catalog-navigation-button"
          disabled={decisionLoading}
          onClick={() => {
            setSelectedApplication(null);
            setError("");
            setSuccess("");
            void loadApplications();
          }}
        >
          ← К списку заявок
        </button>

        <h2>Заявка {application.id}</h2>

        <div className="bank-application-card">
          <div className="bank-application-card__header">
            <h3>{application.company_name}</h3>
            <span className="bank-application-status">
              {application.status_label}
            </span>
          </div>

          <p>ИНН: {application.company_inn}</p>
          <p>
            Кредитный продукт: {productName(application.product_id)}
          </p>
          <p>Сумма кредита: {formatAmount(application.amount)}</p>
          <p>
            Срок кредита:{" "}
            {application.term_months === null
              ? "Не указан"
              : `${application.term_months} мес.`}
          </p>
          <p>
            Цель кредитования: {application.purpose || "Не указана"}
          </p>
          <p>Этап: {application.stage_label}</p>
          <p>Следующий шаг: {application.next_step}</p>
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Результаты скоринга</h3>

          {application.score ? (
            <>
              <p>
                <strong>Уровень риска:</strong>{" "}
                {riskLabels[application.score.risk_class]}
              </p>
              <p>
                <strong>Вероятность дефолта:</strong>{" "}
                {(application.score.score * 100).toFixed(2)}%
              </p>
              <p>
                <strong>Баллы:</strong>{" "}
                {application.score.points_total}
              </p>
              <p>
                <strong>Версия модели:</strong>{" "}
                {application.score.model_version}
              </p>

              <h4>Факторы оценки</h4>

              {application.score.factors.length > 0 ? (
                <ul>
                  {application.score.factors.map((factor, index) => (
                    <li key={`${factor.name}-${index}`}>
                      <strong>{factor.name}</strong>: {factor.comment}{" "}
                      ({factor.impact === "increases_risk"
                        ? "повышает риск"
                        : "снижает риск"})
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Факторы оценки отсутствуют.</p>
              )}
            </>
          ) : (
            <p>Результаты скоринга пока недоступны.</p>
          )}
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Проверки заявки</h3>

          {application.checks.length === 0 ? (
            <p>Результатов проверок пока нет.</p>
          ) : (
            <ul>
              {application.checks.map((check, index) => (
                <li key={`${check.type}-${index}`}>
                  <strong>{check.type}</strong>: {check.summary}{" "}
                  ({check.outcome})
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Решение сотрудника</h3>

          {application.decision && (
            <div className="bank-saved-comment">
              <p>
                <strong>Результат:</strong>{" "}
                {application.decision.outcome}
              </p>
              <p>
                <strong>Причина:</strong>{" "}
                {application.decision.reason}
              </p>
              {application.decision.comment && (
                <p>
                  <strong>Комментарий:</strong>{" "}
                  {application.decision.comment}
                </p>
              )}
            </div>
          )}

          {success && (
            <p role="status" style={{ color: "#2e7d32" }}>
              {success}
            </p>
          )}

          {error && (
            <p className="bank-form-error" role="alert">
              {error}
            </p>
          )}

          {canDecide ? (
            <>
              <label
                className="bank-comment-label"
                htmlFor="bank-decision-comment"
              >
                Комментарий к решению
              </label>

              <textarea
                id="bank-decision-comment"
                className="bank-comment-input"
                value={commentInput}
                maxLength={2000}
                onChange={(event) => {
                  setCommentInput(event.target.value);
                  setError("");
                }}
                placeholder="Укажите причину решения или необходимые уточнения"
                rows={4}
                disabled={decisionLoading}
              />

              <div className="bank-detail-section">
                <h4>Поля для запроса уточнения</h4>

                {clarificationFields.map((field) => (
                  <label
                    key={field.value}
                    style={{
                      display: "block",
                      marginBottom: "10px",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={requestedFields.includes(field.value)}
                      onChange={() => toggleRequestedField(field.value)}
                      disabled={decisionLoading}
                    />{" "}
                    {field.label}
                  </label>
                ))}
              </div>

              <div className="bank-decision-actions">
                <button
                  type="button"
                  className="bank-decision-button bank-decision-button--approve"
                  disabled={decisionLoading}
                  onClick={() => void decide("approved")}
                >
                  {decisionLoading ? "Сохранение..." : "Одобрить"}
                </button>

                <button
                  type="button"
                  className="bank-decision-button bank-decision-button--reject"
                  disabled={decisionLoading}
                  onClick={() => void decide("rejected")}
                >
                  Отклонить
                </button>

                <button
                  type="button"
                  className="bank-decision-button"
                  disabled={decisionLoading}
                  onClick={() => void decide("clarification")}
                >
                  Запросить уточнение
                </button>
              </div>
            </>
          ) : (
            <p>
              Принятие решения сейчас недоступно для этой заявки.
            </p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="bank-dashboard">
      <h2>Заявки клиентов</h2>
      <p>
        Просмотр и обработка кредитных заявок,
        поступивших в систему банка.
      </p>

      <button
        type="button"
        className="catalog-navigation-button"
        disabled={loading || detailsLoading}
        onClick={() => void loadApplications()}
      >
        Обновить список
      </button>

      <div className="bank-filters">
        {filters.map((item) => (
          <button
            key={item.value}
            type="button"
            className={
              filter === item.value ? "bank-filter--active" : ""
            }
            onClick={() => setFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="bank-form-error" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p>Загрузка заявок...</p>
      ) : filteredApplications.length === 0 ? (
        <p>Заявок с выбранным статусом нет.</p>
      ) : (
        <div className="bank-application-list">
          {filteredApplications.map((application) => (
            <article
              className="bank-application-card"
              key={application.id}
            >
              <div className="bank-application-card__header">
                <h3>{application.company_name}</h3>

                <span className="bank-application-status">
                  {application.status_label}
                </span>
              </div>

              <p>Номер заявки: {application.id}</p>
              <p>
                Кредитный продукт:{" "}
                {productName(application.product_id)}
              </p>
              <p>Сумма: {formatAmount(application.amount)}</p>
              <p>Этап: {application.stage_label}</p>

              <button
                type="button"
                className="catalog-navigation-button"
                disabled={detailsLoading}
                onClick={() => void openApplication(application.id)}
              >
                {detailsLoading ? "Загрузка..." : "Подробнее"}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
