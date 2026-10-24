import type { HistoryItem } from "../api/types";
import { dateTime } from "../utils/format";
import { useStatusLabels } from "../utils/hooks";
import { ACTOR_LABELS } from "../utils/labels";

type Props = {
  history: HistoryItem[];
  /** Show who made each move and the internal comments (bank workplace). */
  audit?: boolean;
};

/** Status history of an application, newest last. */
export default function Timeline({ history, audit = false }: Props) {
  const labels = useStatusLabels();

  return (
    <ol className="timeline">
      {history.map((item, index) => (
        <li key={`${item.at}-${index}`} className="timeline__item">
          <div className="timeline__head">
            <span className="timeline__status">{labels[item.to_status] ?? item.to_status}</span>
            <time className="timeline__time" dateTime={item.at}>
              {dateTime(item.at)}
            </time>
          </div>
          {audit && (
            <div className="timeline__meta">
              {ACTOR_LABELS[item.actor]}
              {item.comment ? ` · ${item.comment}` : ""}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
