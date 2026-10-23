
import { useState } from "react";

type ApplicationStatus = "new" | "review" | "approved" | "rejected" | "clarification";
type DecisionStatus = "approved" | "rejected" | "clarification";
type Risk = "low" | "medium" | "high";
type BankApplication = {
  id: string;
  companyName: string;
  inn: string;
  productName: string;
  amount: number;
  term: number;
  purpose: string;
  status: ApplicationStatus;
  risk: Risk;
  factors: string[];
  comment: string;
};
type SavedDecision = { status: ApplicationStatus; comment: string };
type Filter = "all" | ApplicationStatus;

const STORAGE_KEY = "bank-decisions-demo-v1";

const demoApplications: BankApplication[] = [
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
    factors: ["Небольшая сумма кредита в рамках демосценария", "Короткий срок кредитования"],
    comment: "",
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
    factors: ["Длительный срок кредитования", "Для оценки требуются дополнительные финансовые данные"],
    comment: "",
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
    factors: ["Недостаточно данных о финансовом состоянии", "Требуется дополнительная проверка"],
    comment: "",
  },
];

const statusLabels: Record<ApplicationStatus, string> = {
  new: "Новая",
  review: "На рассмотрении",
  approved: "Одобрена",
  rejected: "Отклонена",
  clarification: "Требует уточнения",
};
const riskLabels: Record<Risk, string> = {
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

function loadApplications(): BankApplication[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return demoApplications;
    const saved: unknown = JSON.parse(raw);
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return demoApplications;
    const entries = saved as Record<string, unknown>;
    return demoApplications.map((application) => {
      const item = entries[application.id];
      if (!item || typeof item !== "object" || Array.isArray(item)) return application;
      const decision = item as Partial<SavedDecision>;
      const validStatus = decision.status === "approved" || decision.status === "rejected" || decision.status === "clarification";
      if (!validStatus || typeof decision.comment !== "string") return application;
      return { ...application, status: decision.status as DecisionStatus, comment: decision.comment };
    });
  } catch {
    return demoApplications;
  }
}

export default function BankDashboard() {
  const [applications, setApplications] = useState<BankApplication[]>(loadApplications);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [commentInput, setCommentInput] = useState("");
  const [error, setError] = useState("");
  const [storageWarning, setStorageWarning] = useState("");

  const selectedApplication = applications.find((item) => item.id === selectedId);
  const filteredApplications = applications.filter((item) => filter === "all" || item.status === filter);

  function openApplication(application: BankApplication) {
    setSelectedId(application.id);
    setCommentInput(application.comment);
    setError("");
  }

  function decide(status: DecisionStatus) {
    if (!selectedApplication) return;
    const comment = commentInput.trim();
    if (!comment) {
      setError("Напишите комментарий к решению.");
      return;
    }
    const next = applications.map((item) =>
      item.id === selectedApplication.id ? { ...item, status, comment } : item
    );
    setApplications(next);
    setError("");
    const saved: Record<string, SavedDecision> = {};
    next.forEach((item) => {
      if (item.status === "approved" || item.status === "rejected" || item.status === "clarification") {
        saved[item.id] = { status: item.status, comment: item.comment };
      }
    });
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
      setStorageWarning("");
    } catch {
      setStorageWarning("Решение отображается, но браузер не разрешил сохранить его. После обновления оно может исчезнуть.");
    }
  }

  if (selectedApplication) {
    const canDecide = selectedApplication.status === "new" || selectedApplication.status === "review" || selectedApplication.status === "clarification";
    return (
      <section className="bank-dashboard">
        <button type="button" className="catalog-navigation-button" onClick={() => setSelectedId(null)}>
          ← К списку заявок
        </button>

        <h2>Заявка {selectedApplication.id}</h2>

        <div className="bank-application-card">
          <div className="bank-application-card__header">
            <h3>{selectedApplication.companyName}</h3>
            <span className="bank-application-status">{statusLabels[selectedApplication.status]}</span>
          </div>

          <p>ИНН: {selectedApplication.inn}</p>
          <p>Кредитный продукт: {selectedApplication.productName}</p>
          <p>Сумма кредита: {selectedApplication.amount.toLocaleString("ru-RU")} ₽</p>
          <p>Срок кредита: {selectedApplication.term} мес.</p>
          <p>Цель кредитования: {selectedApplication.purpose}</p>
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Демонстрационный скоринг</h3>
          <p><strong>Уровень риска:</strong> {riskLabels[selectedApplication.risk]}</p>
          <h4>Факторы оценки</h4>
          <ul>{selectedApplication.factors.map((factor) => <li key={factor}>{factor}</li>)}</ul>
          <p className="bank-demo-note">Это пример оценки для интерфейса, а не результат скорингового сервиса или реальное кредитное решение.</p>
        </div>

        <div className="bank-application-card bank-detail-section">
          <h3>Решение сотрудника</h3>
          {selectedApplication.comment && (
            <div className="bank-saved-comment">
              <strong>Последний комментарий:</strong>
              <p>{selectedApplication.comment}</p>
            </div>
          )}
          {canDecide ? (
            <>
              <label className="bank-comment-label" htmlFor="bank-decision-comment">Комментарий к решению</label>
              <textarea
                id="bank-decision-comment"
                className="bank-comment-input"
                value={commentInput}
                maxLength={1000}
                onChange={(event) => { setCommentInput(event.target.value); setError(""); }}
                placeholder="Укажите причину решения или необходимые уточнения"
                rows={4}
              />
              {error && <p className="bank-form-error" role="alert">{error}</p>}
              <div className="bank-decision-actions">
                <button type="button" className="bank-decision-button bank-decision-button--approve" onClick={() => decide("approved")}>Одобрить</button>
                <button type="button" className="bank-decision-button bank-decision-button--reject" onClick={() => decide("rejected")}>Отклонить</button>
                <button type="button" className="bank-decision-button" disabled={selectedApplication.status === "clarification"} onClick={() => decide("clarification")}>Запросить уточнение</button>
              </div>
            </>
          ) : <p>Решение принято: <strong>{statusLabels[selectedApplication.status]}</strong></p>}
          {storageWarning && <p className="bank-form-error" role="alert">{storageWarning}</p>}
        </div>
      </section>
    );
  }

  return (
    <section className="bank-dashboard">
      <h2>Заявки клиентов</h2>
      <p>Просмотр и обработка кредитных заявок (демонстрационные данные).</p>
      <div className="bank-filters">
        {filters.map((item) => (
          <button key={item.value} type="button" className={filter === item.value ? "bank-filter--active" : ""} onClick={() => setFilter(item.value)}>
            {item.label}
          </button>
        ))}
      </div>

      <div className="bank-application-list">
        {filteredApplications.length === 0 && <p>Заявок с выбранным статусом нет.</p>}
        {filteredApplications.map((application) => (
          <article className="bank-application-card" key={application.id}>
            <div className="bank-application-card__header">
              <h3>{application.companyName}</h3>
              <span className="bank-application-status">{statusLabels[application.status]}</span>
            </div>
            <p>Номер заявки: {application.id}</p>
            <p>Кредитный продукт: {application.productName}</p>
            <p>Сумма: {application.amount.toLocaleString("ru-RU")} ₽</p>
            {application.comment && <p><strong>Комментарий:</strong> {application.comment}</p>}
            <button type="button" className="catalog-navigation-button" onClick={() => openApplication(application)}>Подробнее</button>
          </article>
        ))}
      </div>
    </section>
  );
}
