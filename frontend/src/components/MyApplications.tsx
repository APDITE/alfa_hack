
import { useState } from "react";
import type { CreditApplication } from "../types/application";
import {
  getApplications,
  deleteApplication,
} from "../utils/applicationStorage";

type MyApplicationsProps = {
  onEdit: (application: CreditApplication) => void;
};

export default function MyApplications({
  onEdit,
}: MyApplicationsProps) {
  const [applications, setApplications] = useState<CreditApplication[]>(
    getApplications
  );

  function handleDelete(id: string) {
    const confirmed = window.confirm(
      "Вы уверены, что хотите удалить черновик?"
    );

    if (!confirmed) return;

    try {
      deleteApplication(id);
      setApplications(getApplications());
    } catch {
      window.alert("Не удалось удалить черновик.");
    }
  }

  return (
    <section>
      <h2>Мои заявки</h2>
      <p>Здесь отображаются сохранённые черновики.</p>

      {applications.length === 0 ? (
        <p>У вас пока нет сохранённых заявок.</p>
      ) : (
        <div className="application-list">
          {applications.map((application) => (
            <article className="application-card" key={application.id}>
              <div className="application-card__header">
                <h3>{application.productName}</h3>
                <span className="application-status">Черновик</span>
              </div>

              <p>{application.companyName}</p>
              <p>
                Сумма: {application.amount.toLocaleString("ru-RU")} ₽
              </p>
              <p>Срок: {application.term} мес.</p>

              <div className="application-card__actions">
                <button
                  type="button"
                  className="application-edit-button"
                  onClick={() => onEdit(application)}
                >
                  Редактировать
                </button>

                <button
                  type="button"
                  className="application-delete-button"
                  onClick={() => handleDelete(application.id)}
                >
                  Удалить
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
