import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { OpsSummary } from "../api/types";
import { usePolling } from "../utils/hooks";

const TITLES: Record<OpsSummary["status"], string> = {
  ok: "Конвейер работает штатно",
  warning: "В конвейере есть проблемы",
  critical: "Конвейер остановился",
};

/** Pipeline health for employees (GET /api/ops/summary); same thresholds as the alerts. */
export default function PipelineHealth() {
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setSummary(await api.opsSummary());
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);
  usePolling(load, 5000);

  if (failed && !summary) {
    return <div className="health health--warning">Состояние конвейера недоступно</div>;
  }
  if (!summary) return null;

  return (
    <div className={`health health--${summary.status}`} role="status">
      <div className="health__title">{TITLES[summary.status]}</div>
      <div className="muted small">
        Готово к обработке: {summary.ready_jobs} · Ждут внешний сервис: {summary.waiting_external} ·
        На ручной проверке: {summary.manual_review} · Ошибок за сутки: {summary.failed_jobs_24h}
      </div>
      {summary.alerts.length > 0 && (
        <ul className="health__alerts">
          {summary.alerts.map((alert) => (
            <li key={alert.text}>{alert.text}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
