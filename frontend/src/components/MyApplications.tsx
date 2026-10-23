import { useState } from "react";
import type { ApplicationStatus, CreditApplication } from "../types/application";
import {
  getApplications,
  deleteApplication,
  updateApplication,
} from "../utils/applicationStorage";

type MyApplicationsProps = {
  onEdit: (application: CreditApplication) => void;
};

const statusLabels: Record<ApplicationStatus, string> = {
  draft: "Черновик",
  submitted: "Отправлена (демо)",
  review: "На рассмотрении",
  clarification: "Требуется уточнение",
  approved: "Одобрена",
  rejected: "Отклонена",
  offer: "Есть предложение",
  accepted: "Предложение принято",
  declined: "Предложение отклонено",
};

export default function MyApplications({ onEdit }: MyApplicationsProps) {
  const [applications, setApplications] = useState<CreditApplication[]>(getApplications);
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  function refresh() {
    setApplications(getApplications());
    setError("");
  }

  function handleDelete(application: CreditApplication) {
    if (application.status !== "draft") return;
    if (!window.confirm("Удалить черновик заявки?")) return;
    try {
      deleteApplication(application.id);
      refresh();
    } catch {
      setError("Не удалось удалить черновик.");
    }
  }

  function changeApplication(application: CreditApplication, status: ApplicationStatus) {
    try {
      if (status === "submitted" && application.status !== "draft" && application.status !== "clarification") return;
      if ((status === "accepted" || status === "declined") && application.status !== "offer") return;
      const clarificationReply = replies[application.id]?.trim();
      if (application.status === "clarification" && status === "submitted" && !clarificationReply) {
        setError("Введите ответ на запрос уточнений.");
        return;
      }
      if (application.status === "draft" && status === "submitted" &&
          !window.confirm("Отправить заявку? В демоверсии она сохранится только в этом браузере.")) return;
      updateApplication({
        ...application,
        status,
        submittedAt: application.submittedAt ?? new Date().toISOString(),
        ...(application.status === "clarification" && status === "submitted"
          ? { clarificationReply } : {}),
      });
      refresh();
    } catch {
      setError("Не удалось изменить заявку.");
    }
  }

  return (
    <section>
      <h2>Мои заявки</h2>
      <p>Демонстрационный режим: заявки сохраняются в этом браузере и не отправляются в банк.</p>
      {error && <p role="alert" style={{ color: "#c62828" }}>{error}</p>}
      {applications.length === 0 ? (
        <p>У вас пока нет заявок.</p>
      ) : (
        <div className="application-list">
          {applications.map((application) => (
            <article className="application-card" key={application.id}>
              <div className="application-card__header">
                <h3>{application.productName}</h3>
                <span className="application-status">
                  {statusLabels[application.status] ?? application.status}
                </span>
              </div>
              <p>{application.companyName}</p>
              <p>Сумма: {application.amount.toLocaleString("ru-RU")} ₽</p>
              <p>Срок: {application.term} мес.</p>
              <p>Цель: {application.purpose}</p>
              <p>Номер заявки: {application.id}</p>
              {application.submittedAt && (
                <p>Дата отправки: {new Date(application.submittedAt).toLocaleString("ru-RU")}</p>
              )}
              {application.clarificationRequest && (
                <p><strong>Запрос сотрудника:</strong> {application.clarificationRequest}</p>
              )}
              {application.clarificationReply && (
                <p><strong>Ваш ответ:</strong> {application.clarificationReply}</p>
              )}
              {application.offerDetails && (
                <p><strong>Предложение:</strong> {application.offerDetails}</p>
              )}
              <div className="application-card__actions">
                {application.status === "draft" && (
                  <>
                    <button type="button" className="application-edit-button" onClick={() => onEdit(application)}>
                      Редактировать
                    </button>
                    <button type="button" onClick={() => changeApplication(application, "submitted")}>
                      Отправить заявку (демо)
                    </button>
                    <button type="button" className="application-delete-button" onClick={() => handleDelete(application)}>
                      Удалить
                    </button>
                  </>
                )}
                {application.status === "clarification" && (
                  <div>
                    <label htmlFor={`reply-${application.id}`}>Ответ на запрос уточнений</label>
                    <textarea
                      id={`reply-${application.id}`}
                      value={replies[application.id] ?? ""}
                      onChange={(event) => setReplies((current) => ({ ...current, [application.id]: event.target.value }))}
                    />
                    <button type="button" onClick={() => changeApplication(application, "submitted")}>
                      Отправить уточнение (демо)
                    </button>
                  </div>
                )}
                {application.status === "offer" && (
                  <>
                    <button type="button" onClick={() => changeApplication(application, "accepted")}>Принять предложение (демо)</button>
                    <button type="button" onClick={() => changeApplication(application, "declined")}>Отклонить предложение (демо)</button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
