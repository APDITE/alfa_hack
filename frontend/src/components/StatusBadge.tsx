import type { ApplicationSummary } from "../api/types";
import { statusTone } from "../utils/labels";

type Props = {
  application: Pick<ApplicationSummary, "status" | "status_label" | "client_stage">;
  tone?: string;
};

export default function StatusBadge({ application, tone }: Props) {
  const resolved = tone ?? statusTone(application.status, application.client_stage);
  return <span className={`badge badge--${resolved}`}>{application.status_label}</span>;
}
