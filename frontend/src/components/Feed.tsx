import type { Feed as FeedData } from "../api/types";
import { dateTime } from "../utils/format";

type Props = {
  feed: FeedData | null;
  error: string;
  onOpenApplication: (id: string) => void;
};

/** Notifications about the client's applications, newest first. */
export default function Feed({ feed, error, onOpenApplication }: Props) {
  return (
    <section className="card notifications">
      <h2>Уведомления</h2>
      <p className="muted">События по вашим заявкам: отправка, запросы банка, решение, выдача.</p>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : !feed ? (
        <p className="muted">Загружаем уведомления…</p>
      ) : feed.events.length === 0 ? (
        <p className="empty">Уведомлений пока нет — они появятся после отправки заявки.</p>
      ) : (
        <ul className="events">
          {feed.events.map((event) => (
            <li key={event.id} className={`event${event.read ? "" : " event--unread"}`}>
              <div className="event__head">
                <strong>{event.title}</strong>
                <time dateTime={event.created_at}>{dateTime(event.created_at)}</time>
              </div>
              <p>{event.text}</p>
              {event.application_id && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onOpenApplication(event.application_id ?? "")}
                >
                  Открыть заявку
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
