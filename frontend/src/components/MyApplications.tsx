
import { useCallback, useEffect, useState } from "react";
import {
  getApplications,
  getApplication,
  submitApplication,
  respondToOffer,
  signApplication,
  type ApplicationSummary,
  type ApplicationDetail,
} from "../api/applications";
import type { CreditApplication } from "../types/application";

type MyApplicationsProps = {
  onEdit: (application: CreditApplication) => void;
};

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

export default function MyApplications({
  onEdit,
}: MyApplicationsProps) {
  const [applications, setApplications] = useState<ApplicationSummary[]>([]);
  const [details, setDetails] = useState<
    Record<string, ApplicationDetail>
  >({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

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

  async function handleDetails(id: string) {
    if (details[id]) {
      setDetails((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
      return;
    }

    setBusyId(id);
    setError("");

    try {
      const detail = await getApplication(id);

      setDetails((current) => ({
        ...current,
        [id]: detail,
      }));
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setBusyId(null);
    }
  }

  async function handleEdit(application: ApplicationSummary) {
    setBusyId(application.id);
    setError("");

    try {
      const detail = await getApplication(application.id);

      if (!detail.available_actions.includes("edit")) {
        throw new Error("Редактирование этой заявки недоступно.");
      }

      const editableApplication = {
        id: detail.id,
        productName: productName(detail.product_id),
        amount: detail.amount ?? 0,
        term: detail.term_months ?? 0,
        purpose: detail.purpose ?? "",
        companyName: detail.company_name,
        inn: detail.company_inn,
        status: "draft",
        createdAt: detail.created_at,
      } as CreditApplication;

      onEdit(editableApplication);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setBusyId(null);
    }
  }

  async function handleSubmit(application: ApplicationSummary) {
    if (
      !window.confirm(
        "Отправить заявку в банк? После отправки редактирование черновика будет недоступно."
      )
    ) {
      return;
    }

    setBusyId(application.id);
    setError("");

    try {
      const detail = await getApplication(application.id);

      if (!detail.available_actions.includes("submit")) {
        throw new Error(
          "Заявку сейчас нельзя отправить. Проверьте заполненные данные."
        );
      }

      const idempotencyKey = crypto.randomUUID();

      await submitApplication(application.id, idempotencyKey);

      setDetails({});
      await loadApplications();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setBusyId(null);
    }
  }

  async function handleOffer(id: string, accept: boolean) {
    const message = accept
      ? "Принять предложение банка?"
      : "Отказаться от предложения банка?";

    if (!window.confirm(message)) {
      return;
    }

    setBusyId(id);
    setError("");

    try {
      const detail = await getApplication(id);
      const action = accept ? "accept" : "decline";

      if (!detail.available_actions.includes(action)) {
        throw new Error("Это действие сейчас недоступно.");
      }

      const updated = await respondToOffer(id, accept);

      setDetails((current) => ({
        ...current,
        [id]: updated,
      }));

      await loadApplications();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setBusyId(null);
    }
  }

  async function handleSign(id: string) {
    if (!window.confirm("Подписать документы по заявке?")) {
      return;
    }

    setBusyId(id);
    setError("");

    try {
      const detail = await getApplication(id);

      if (!detail.available_actions.includes("sign")) {
        throw new Error("Подписание сейчас недоступно.");
      }

      const updated = await signApplication(id);

      setDetails((current) => ({
        ...current,
        [id]: updated,
      }));

      await loadApplications();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <h2>Мои заявки</h2>

      <p>
        Здесь отображаются ваши кредитные заявки,
        сохранённые в системе банка.
      </p>

      <button
        type="button"
        className="application-action-button"
        onClick={() => void loadApplications()}
        disabled={loading || busyId !== null}
      >
        Обновить список
      </button>

      {error && (
        <p role="alert" style={{ color: "#c62828" }}>
          {error}
        </p>
      )}

      {loading ? (
        <p>Загрузка заявок...</p>
      ) : applications.length === 0 ? (
        <p>У вас пока нет заявок.</p>
      ) : (
        <div className="application-list">
          {applications.map((application) => {
            const detail = details[application.id];
            const busy = busyId !== null;

            return (
              <article
                className="application-card"
                key={application.id}
              >
                <div className="application-card__header">
                  <h3>
                    {productName(application.product_id)}
                  </h3>

                  <span className="application-status">
                    {application.status_label}
                  </span>
                </div>

                <p>{application.company_name}</p>

                <p>
                  Сумма: {formatAmount(application.amount)}
                </p>

                <p>
                  Срок:{" "}
                  {application.term_months === null
                    ? "Не указан"
                    : `${application.term_months} мес.`}
                </p>

                <p>Этап: {application.stage_label}</p>

                <p>Номер заявки: {application.id}</p>

                <p>
                  Создана:{" "}
                  {new Date(
                    application.created_at
                  ).toLocaleString("ru-RU")}
                </p>

                {detail && (
                  <div>
                    <p>
                      <strong>Цель:</strong>{" "}
                      {detail.purpose || "Не указана"}
                    </p>

                    <p>
                      <strong>Следующий шаг:</strong>{" "}
                      {detail.next_step}
                    </p>

                    {detail.submitted_at && (
                      <p>
                        <strong>Отправлена:</strong>{" "}
                        {new Date(
                          detail.submitted_at
                        ).toLocaleString("ru-RU")}
                      </p>
                    )}

                    {detail.decision && (
                      <div>
                        <p>
                          <strong>Решение банка:</strong>{" "}
                          {detail.decision.reason}
                        </p>
                      </div>
                    )}

                    {detail.clarification && (
                      <p>
                        <strong>Запрос банка:</strong>{" "}
                        {detail.clarification.message}
                      </p>
                    )}
                  </div>
                )}

                <div className="application-card__actions">
                  <button
                    type="button"
                    className="application-action-button"
                    disabled={busy}
                    onClick={() =>
                      void handleDetails(application.id)
                    }
                  >
                    {busyId === application.id
                      ? "Загрузка..."
                      : detail
                        ? "Скрыть подробности"
                        : "Подробнее"}
                  </button>

                  {application.status === "draft" && (
                    <>
                      <button
                        type="button"
                        className="application-edit-button"
                        disabled={busy}
                        onClick={() =>
                          void handleEdit(application)
                        }
                      >
                        Редактировать
                      </button>

                      <button
                        type="button"
                        className="application-action-button"
                        disabled={busy}
                        onClick={() =>
                          void handleSubmit(application)
                        }
                      >
                        Отправить заявку
                      </button>
                    </>
                  )}

                  {detail?.available_actions.includes("accept") && (
                    <button
                      type="button"
                      className="application-action-button"
                      disabled={busy}
                      onClick={() =>
                        void handleOffer(application.id, true)
                      }
                    >
                      Принять предложение
                    </button>
                  )}

                  {detail?.available_actions.includes("decline") && (
                    <button
                      type="button"
                      className="application-action-button"
                      disabled={busy}
                      onClick={() =>
                        void handleOffer(application.id, false)
                      }
                    >
                      Отказаться
                    </button>
                  )}

                  {detail?.available_actions.includes("sign") && (
                    <button
                      type="button"
                      className="application-action-button"
                      disabled={busy}
                      onClick={() =>
                        void handleSign(application.id)
                      }
                    >
                      Подписать документы
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
