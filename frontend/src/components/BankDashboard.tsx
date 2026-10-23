
import { useState } from "react";

type BankApplication = {
  id: string;
  companyName: string;
  productName: string;
  amount: number;
  status: "new" | "review";
};

const demoApplications: BankApplication[] = [
  {
    id: "APP-001",
    companyName: "ООО «Ромашка»",
    productName: "Оборотный кредит",
    amount: 1000000,
    status: "new",
  },
  {
    id: "APP-002",
    companyName: "ООО «Вектор»",
    productName: "Инвестиционный кредит",
    amount: 3500000,
    status: "review",
  },
  {
    id: "APP-003",
    companyName: "ООО «Старт»",
    productName: "Оборотный кредит",
    amount: 750000,
    status: "new",
  },
];

type Filter = "all" | "new" | "review";

export default function BankDashboard() {
  const [filter, setFilter] = useState<Filter>("all");

  const filteredApplications = demoApplications.filter(
    (application) =>
      filter === "all" || application.status === filter
  );

  return (
    <section className="bank-dashboard">
      <h2>Заявки клиентов</h2>
      <p>Просмотр и обработка кредитных заявок.</p>

      <div className="bank-filters">
        <button
          type="button"
          className={filter === "all" ? "bank-filter--active" : ""}
          onClick={() => setFilter("all")}
        >
          Все
        </button>

        <button
          type="button"
          className={filter === "new" ? "bank-filter--active" : ""}
          onClick={() => setFilter("new")}
        >
          Новые
        </button>

        <button
          type="button"
          className={filter === "review" ? "bank-filter--active" : ""}
          onClick={() => setFilter("review")}
        >
          На рассмотрении
        </button>
      </div>

      <div className="bank-application-list">
        {filteredApplications.map((application) => (
          <article
            className="bank-application-card"
            key={application.id}
          >
            <div className="bank-application-card__header">
              <h3>{application.companyName}</h3>
              <span className="bank-application-status">
                {application.status === "new"
                  ? "Новая"
                  : "На рассмотрении"}
              </span>
            </div>

            <p>Номер: {application.id}</p>
            <p>Продукт: {application.productName}</p>
            <p>
              Сумма:{" "}
              {application.amount.toLocaleString("ru-RU")} ₽
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
