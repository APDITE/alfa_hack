import { useCallback, useEffect, useState } from "react";

import { api, errorText } from "../api/client";
import type { ApplicationStatus, ApplicationSummary, Product } from "../api/types";
import { money, months, timeAgo } from "../utils/format";
import { usePolling } from "../utils/hooks";
import { IN_PROGRESS, PRODUCT_NAMES, RISK_LABELS } from "../utils/labels";
import BankApplication from "./BankApplication";
import DemoPanel from "./DemoPanel";
import PipelineHealth from "./PipelineHealth";
import StatusBadge from "./StatusBadge";

type Queue = {
  id: string;
  label: string;
  statuses: ApplicationStatus[] | null;
  hint: string;
};

const QUEUES: Queue[] = [
  {
    id: "manual",
    label: "Ждут решения",
    statuses: ["manual_review"],
    hint: "Автоматика передала эти заявки сотруднику. Сначала самые давние.",
  },
  {
    id: "processing",
    label: "В обработке",
    statuses: IN_PROGRESS,
    hint: "Конвейер проверяет данные и считает решение.",
  },
  {
    id: "clarification",
    label: "Ждут клиента",
    statuses: ["clarification_required"],
    hint: "Банк запросил у клиента недостающие данные.",
  },
  {
    id: "approved",
    label: "Одобрены",
    statuses: ["approved", "counter_offer", "signing", "issued"],
    hint: "Одобрены, ждут подписания или уже выданы.",
  },
  {
    id: "closed",
    label: "Отказ и отзыв",
    statuses: ["rejected", "withdrawn"],
    hint: "Закрытые без выдачи.",
  },
  { id: "all", label: "Все", statuses: null, hint: "Все заявки, кроме черновиков клиентов." },
];

function inQueue(queue: Queue, application: ApplicationSummary): boolean {
  return queue.statuses === null || queue.statuses.includes(application.status);
}

export default function BankDashboard() {
  const [applications, setApplications] = useState<ApplicationSummary[] | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [queueId, setQueueId] = useState("manual");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setApplications(await api.applications());
      setError("");
    } catch (caught) {
      setError(errorText(caught));
    }
  }, []);

  useEffect(() => {
    void load();
    api
      .products()
      .then(setProducts)
      .catch(() => undefined);
  }, [load]);
  usePolling(load, selectedId ? null : 4000);

  if (selectedId) {
    return (
      <BankApplication
        id={selectedId}
        products={products}
        onBack={() => {
          setSelectedId(null);
          void load();
        }}
        onDecided={() => void load()}
      />
    );
  }

  const queue = QUEUES.find((q) => q.id === queueId) ?? QUEUES[0];
  const visible = (applications ?? []).filter((a) => inQueue(queue, a));
  if (queue.id === "manual") visible.sort((a, b) => a.updated_at.localeCompare(b.updated_at));

  return (
    <section className="card bank-dashboard">
      <div className="section-head section-head--top">
        <div>
          <h2>Кредитные заявки</h2>
          <p className="muted">Очередь обновляется автоматически.</p>
        </div>
        <DemoPanel />
      </div>

      <PipelineHealth />

      <div className="queues" role="tablist" aria-label="Очереди заявок">
        {QUEUES.map((item) => {
          const count = (applications ?? []).filter((a) => inQueue(item, a)).length;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === queue.id}
              className={`queue${item.id === queue.id ? " queue--active" : ""}${item.id === "manual" && count > 0 ? " queue--attention" : ""}`}
              onClick={() => setQueueId(item.id)}
            >
              {item.label}
              <span className="queue__count">{count}</span>
            </button>
          );
        })}
      </div>
      <p className="muted small">{queue.hint}</p>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {applications === null ? (
        <p className="muted">Загружаем заявки…</p>
      ) : visible.length === 0 ? (
        <p className="empty">В этой очереди пока пусто.</p>
      ) : (
        <div className="table-wrap">
          <table className="queue-table">
            <thead>
              <tr>
                <th>Компания</th>
                <th>Продукт</th>
                <th>Сумма и срок</th>
                <th>Риск</th>
                <th>Статус</th>
                <th>Изменена</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((application) => (
                <tr
                  key={application.id}
                  tabIndex={0}
                  onClick={() => setSelectedId(application.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") setSelectedId(application.id);
                  }}
                >
                  <td>
                    <strong>{application.company_name}</strong>
                    <div className="muted small">ИНН {application.company_inn}</div>
                  </td>
                  <td>{PRODUCT_NAMES[application.product_id]}</td>
                  <td>
                    {money(application.amount)}
                    <div className="muted small">{months(application.term_months)}</div>
                  </td>
                  <td>
                    {application.risk_class ? (
                      <span className={`badge badge--risk-${application.risk_class}`}>
                        {RISK_LABELS[application.risk_class]}
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    <StatusBadge
                      application={application}
                      tone={application.status === "manual_review" ? "warning" : undefined}
                    />
                  </td>
                  <td className="muted small">{timeAgo(application.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
