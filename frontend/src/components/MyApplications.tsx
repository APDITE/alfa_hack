import type { ApplicationDetail, ApplicationSummary } from "../api/types";
import ApplicationCard from "./ApplicationCard";

type Props = {
  applications: ApplicationSummary[];
  details: Record<string, ApplicationDetail>;
  highlightId: string | null;
  onChanged: (detail: ApplicationDetail) => void;
  onEdit: (detail: ApplicationDetail) => void;
  onNew: () => void;
};

// Applications that wait for the client come first, then the rest by last change.
const PRIORITY: Record<ApplicationSummary["client_stage"], number> = {
  action_required: 0,
  decision_ready: 0,
  signing: 0,
  filling: 1,
  in_review: 2,
  completed: 3,
};

export default function MyApplications({
  applications,
  details,
  highlightId,
  onChanged,
  onEdit,
  onNew,
}: Props) {
  const sorted = [...applications].sort(
    (a, b) =>
      PRIORITY[a.client_stage] - PRIORITY[b.client_stage] ||
      b.updated_at.localeCompare(a.updated_at),
  );
  const waiting = applications.filter((a) => PRIORITY[a.client_stage] === 0).length;

  return (
    <section className="card">
      <div className="section-head">
        <div>
          <h2>Мои заявки</h2>
          <p className="muted">
            {waiting > 0
              ? `Ждут вашего действия: ${waiting}. Статусы обновляются автоматически.`
              : "Статусы обновляются автоматически — обновлять страницу не нужно."}
          </p>
        </div>
        <button type="button" className="button button--primary" onClick={onNew}>
          Новая заявка
        </button>
      </div>

      {sorted.length === 0 ? (
        <div className="empty">
          <p>Заявок пока нет. Подберите продукт и отправьте первую заявку — это займёт пару минут.</p>
          <button type="button" className="button button--primary" onClick={onNew}>
            Подобрать кредит
          </button>
        </div>
      ) : (
        <div className="application-list">
          {sorted.map((summary) => (
            <ApplicationCard
              key={summary.id}
              summary={summary}
              detail={details[summary.id]}
              highlighted={summary.id === highlightId}
              onChanged={onChanged}
              onEdit={onEdit}
            />
          ))}
        </div>
      )}
    </section>
  );
}
