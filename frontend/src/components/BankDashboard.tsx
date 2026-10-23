
import { useState } from "react";

type ApplicationStatus =
  | "new"
  | "review"
  | "approved"
  | "rejected"
  | "clarification";

type BankApplication = {
  id: string;
  companyName: string;
  inn: string;
  productName: string;
  amount: number;
  term: number;
  purpose: string;
  status: ApplicationStatus;
  risk: "low" | "medium" | "high";
  factors: string[];
};

type Filter = "all" | ApplicationStatus;

const initialApplications: BankApplication[] = [
  {
    id: "APP-001",
    companyName: "ООО «Ромашка»",
    inn: "1234567890",
    productName: "Оборотный кредит",
    amount: 1000000,
    term: 12,
    purpose: "Закупка товаров для расширения ассортимента",
    status: "new",
    risk: "low",
    factors: [
      "Небольшая сумма относительно демонстрационного лимита",
      "Короткий срок кредитования",
    ],
  },
  {
    id: "APP-002",
    companyName: "ООО «Вектор»",
    inn: "9876543210",
    productName: "Кредит на оборудование",
    amount: 3500000,
    term: 36,
    purpose: "Покупка оборудования для производства",
    status: "review",
    risk: "medium",
    factors: [
      "Длительный срок кредитования",
      "Требуется дополнительная проверка финансовых данных",
    ],
  },
  {
    id: "APP-003",
    companyName: "ООО «Старт»",
    inn: "1122334455",
    productName: "Оборотный кредит",
    amount: 750000,
    term: 6,
    purpose: "Пополнение оборотных средств компании",
    status: "new",
    risk: "high",
    factors: [
      "Недостаточно данных о финансовом состоянии компании",
      "Необходима дополнительная проверка",
    ],
  },
];

const statusLabels: Record<ApplicationStatus, string> = {
  new: "Новая",
  review: "На рассмотрении",
  approved: "Одобрена",
  rejected: "Отклонена",
  clarification: "Требует уточнения",
};

const riskLabels = {
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
};

const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "new", label: "Новые" },
  { value: "review", label: "На рассмотрении" },
  { value: "approved", label: "Одобрены" },
  { value: "rejected", label: "Отклонены" },
  { value: "clarification", label: "Требуют уточнения" },
];

export default function BankDashboard() {
  const [applications, setApplications] =
    useState<BankApplication[]>(initialApplications);

  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedApplication = applications.find(
    (application) => application.id === selectedId
  );

  const filteredApplications = applications.filter(
    (application) =>
      filter === "all" || application.status === filter
  );

  function changeStatus(
    id: string,
    status: ApplicationStatus
  ) {
    setApplications((current) =>
      current.map((application) =>
        application.id === id
          ? { ...application, status }
          : application
      )
    );
  }

  if (selectedApplication) {
    const canDecide =
      selectedApplication.status === "new" ||
      selectedApplication.status === "review" ||
      selectedApplication.status === "clarification";

    return (
      <section className="bank-dashboard">
        <button
          type="button"
          className="catalog-navigation-button"
          onClick={() => setSelectedId(null)}
        >
          ← К списку заявок
        </button>

        <h2>Заявка {selectedApplication.id}</h2>

        <div className="bank-application-card">
          <div className="bank-application-card__header">
            <h3>{selectedApplication.companyName}</h3>
            <span className="bank-application-status">
              {statusLabels[selectedApplication.status]}
            </span>
          </div>

          <p>ИНН: {selectedApplication.inn}</p>
          <p>
            Кредитный продукт: {selectedApplication.productName}
          </p>
          <p>
            Сумма кредита:{" "}
            {selectedApplication.amount.toLocaleString("ru-RU")} ₽
          </p>
          <p>Срок кредита: {selectedApplication.term} мес.</p>
          <p>Цель кредитования: {selectedApplication.purpose}</p>
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Результат скоринга</h3>
          <p>
            <strong>Уровень риска:</strong>{" "}
            {riskLabels[selectedApplication.risk]}
          </p>

          <h4>Факторы оценки</h4>
          <ul>
            {selectedApplication.factors.map((factor) => (
              <li key={factor}>{factor}</li>
            ))}
          </ul>

          <p className="bank-demo-note">
            Демонстрационная оценка. Не является результатом
            реального скорингового сервиса или кредитным решением.
          </p>
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Решение сотрудника</h3>

          {canDecide ? (
            <div className="bank-decision-actions">
              <button
                type="button"
                className="bank-decision-button bank-decision-button--approve"
                onClick={() =>
                  changeStatus(selectedApplication.id, "approved")
                }
              >
                Одобрить
              </button>

              <button
                type="button"
                className="bank-decision-button bank-decision-button--reject"
                onClick={() =>
                  changeStatus(selectedApplication.id, "rejected")
                }
              >
                Отклонить
              </button>

              <button
                type="button"
                className="bank-decision-button"
                disabled={
                  selectedApplication.status === "clarification"
                }
                onClick={() =>
                  changeStatus(selectedApplication.id, "clarification")
                }
              >
                Запросить уточнение
              </button>
            </div>
          ) : (
            <p>
              Решение принято:{" "}
              <strong>
                {statusLabels[selectedApplication.status]}
              </strong>
            </p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="bank-dashboard">
      <h2>Заявки клиентов</h2>
      <p>Просмотр и обработка кредитных заявок.</p>

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

      <div className="bank-application-list">
        {filteredApplications.length === 0 ? (
          <p>Заявок с выбранным статусом нет.</p>
        ) : (
          filteredApplications.map((application) => (
            <article
              className="bank-application-card"
              key={application.id}
            >
              <div className="bank-application-card__header">
                <h3>{application.companyName}</h3>
                <span className="bank-application-status">
                  {statusLabels[application.status]}
                </span>
              </div>

              <p>Номер заявки: {application.id}</p>
              <p>
                Кредитный продукт: {application.productName}
              </p>
              <p>
                Сумма:{" "}
                {application.amount.toLocaleString("ru-RU")} ₽
              </p>

              <button
                type="button"
                className="catalog-navigation-button"
                onClick={() => setSelectedId(application.id)}
              >
                Подробнее
              </button>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
