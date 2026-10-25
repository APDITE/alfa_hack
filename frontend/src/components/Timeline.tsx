import { useState } from "react";

import type { HistoryItem } from "../api/types";
import { dateTime } from "../utils/format";
import { useStatusLabels } from "../utils/hooks";
import { ACTOR_LABELS } from "../utils/labels";

type Props = {
  history: HistoryItem[];
  /** Show who made each move and the internal comments (bank workplace). */
  audit?: boolean;
};

type Filter = { id: string; label: string; test: (item: HistoryItem) => boolean };

const NEGOTIATION: Filter = {
  id: "negotiation",
  label: "Переговоры и договор",
  test: (item) => item.kind !== "status",
};

// The client sees the bank as one side; the bank tells the system from the employee.
const CLIENT_FILTERS: Filter[] = [
  { id: "all", label: "Все", test: () => true },
  NEGOTIATION,
  { id: "client", label: "Ваши действия", test: (item) => item.actor === "client" },
  { id: "bank", label: "Банк", test: (item) => item.actor !== "client" },
];

const AUDIT_FILTERS: Filter[] = [
  { id: "all", label: "Все", test: () => true },
  NEGOTIATION,
  { id: "client", label: "Клиент", test: (item) => item.actor === "client" },
  { id: "employee", label: "Сотрудник", test: (item) => item.actor === "employee" },
  { id: "system", label: "Система", test: (item) => item.actor === "system" },
];

/** Status history of an application, newest last, with filters by side and topic. */
export default function Timeline({ history, audit = false }: Props) {
  const labels = useStatusLabels();
  const filters = audit ? AUDIT_FILTERS : CLIENT_FILTERS;
  const [filterId, setFilterId] = useState("all");
  const filter = filters.find((f) => f.id === filterId) ?? filters[0];
  const shown = history.filter(filter.test);

  return (
    <div className="history">
      <div className="history__filters" role="group" aria-label="Фильтр истории">
        {filters.map((f) => {
          const count = history.filter(f.test).length;
          return (
            <button
              key={f.id}
              type="button"
              className={`chip${f.id === filter.id ? " chip--active" : ""}`}
              aria-pressed={f.id === filter.id}
              disabled={count === 0 && f.id !== "all"}
              onClick={() => setFilterId(f.id)}
            >
              {f.label} <span className="chip__count">{count}</span>
            </button>
          );
        })}
      </div>
      <ol className="timeline">
        {shown.map((item, index) => (
          <li key={`${item.at}-${index}`} className={`timeline__item timeline__item--${item.kind}`}>
            <time className="timeline__time" dateTime={item.at}>
              {dateTime(item.at)}
            </time>
            <div>
              <span className="timeline__status">
                {item.kind === "agreement" && item.from_status === item.to_status
                  ? "Новая редакция договора"
                  : (labels[item.to_status] ?? item.to_status)}
              </span>
              {item.details && <div className="timeline__details">{item.details}</div>}
              {audit && (
                <div className="timeline__meta">
                  {ACTOR_LABELS[item.actor]}
                  {item.comment ? ` · ${item.comment}` : ""}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
