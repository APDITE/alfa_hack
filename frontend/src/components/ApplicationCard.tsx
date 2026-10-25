import { useState, type FormEvent } from "react";

import { ApiError, api, errorText } from "../api/client";
import type { ApplicationDetail, ApplicationSummary, ClarificationAnswer, LoanTerms } from "../api/types";
import {
  annuityPayment,
  dateTime,
  groupDigits,
  money,
  months,
  newIdempotencyKey,
  parseInteger,
  percent,
} from "../utils/format";
import { FIELD_LABELS, IN_PROGRESS, PRODUCT_NAMES, PURPOSE_LABELS } from "../utils/labels";
import { cashPlanSummary } from "../utils/cash";
import AgreementPanel from "./AgreementPanel";
import CashCalendar from "./CashCalendar";
import { NegotiationPanel, ProposalForm } from "./Negotiation";
import PaymentScheduleView from "./PaymentScheduleView";
import StatusBadge from "./StatusBadge";
import Timeline from "./Timeline";

type Props = {
  summary: ApplicationSummary;
  detail: ApplicationDetail | undefined;
  highlighted: boolean;
  onChanged: (detail: ApplicationDetail) => void;
  onEdit: (detail: ApplicationDetail) => void;
};

const STEPS = ["Заявка", "Проверка", "Решение", "Подписание", "Деньги на счёте"];

function stepOf(status: ApplicationSummary["status"]): number {
  switch (status) {
    case "draft":
      return 0;
    case "approved":
    case "counter_offer":
    case "rejected":
      return 2;
    case "signing":
      return 3;
    case "issued":
      return 4;
    default:
      return 1;
  }
}

function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

/** Payment day: the saved choice in one line, or the cash calendar to choose it. */
function CashPlanSection({
  detail,
  onChanged,
}: {
  detail: ApplicationDetail;
  onChanged: (detail: ApplicationDetail) => void;
}) {
  const [open, setOpen] = useState(false);
  const plan = detail.cash_plan;
  // Accepting an offer fixes a payment day (the day of the issue) unless the client chose one.
  const defaultDay = plan ? null : (detail.schedule?.payment_day ?? null);
  if (open) {
    return (
      <CashCalendar
        detail={detail}
        onClose={() => setOpen(false)}
        onSaved={(updated) => {
          onChanged(updated);
          setOpen(false);
        }}
      />
    );
  }
  return (
    <div className="cash-plan">
      <div className="cash-plan__text">
        <strong>
          {plan
            ? `Платёж ${plan.payment_day}-го числа`
            : defaultDay
              ? `Платёж ${defaultDay}-го числа — день выдачи`
              : "Дата платежа"}
        </strong>
        <span className="muted small">
          {plan
            ? `Денежный календарь: ${cashPlanSummary(plan)}.`
            : "Подберите день под свои поступления: банк покажет, где возникает кассовый разрыв и сколько стоит перенос платежа."}
        </span>
      </div>
      <button type="button" className="button button--secondary" onClick={() => setOpen(true)}>
        {plan ? "Изменить" : "Открыть денежный календарь"}
      </button>
    </div>
  );
}

function Progress({ status }: { status: ApplicationSummary["status"] }) {
  if (status === "withdrawn") return null;
  const current = stepOf(status);
  return (
    <ol className="steps" aria-label="Этапы заявки">
      {STEPS.map((step, index) => {
        let state = index < current ? "done" : index === current ? "current" : "todo";
        if (status === "rejected" && index === current) state = "failed";
        if (status === "issued" && index === current) state = "done";
        return (
          <li
            key={step}
            className={`steps__item steps__item--${state}`}
            aria-current={state === "current" || state === "failed" ? "step" : undefined}
          >
            <span className="steps__dot">
              {state === "done" ? <CheckIcon /> : state === "failed" ? "×" : index + 1}
            </span>
            <span className="steps__label">{step}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** Offered or signed terms as tiles; the product is shown only when it differs from the request. */
function TermsList({ terms, showProduct }: { terms: LoanTerms; showProduct: boolean }) {
  return (
    <dl className="terms">
      {showProduct && (
        <div className="terms__item terms__item--text">
          <dt>Продукт</dt>
          <dd>{PRODUCT_NAMES[terms.product_id]}</dd>
        </div>
      )}
      <div className="terms__item">
        <dt>Сумма</dt>
        <dd>{money(terms.amount)}</dd>
      </div>
      <div className="terms__item">
        <dt>Срок</dt>
        <dd>{months(terms.term_months)}</dd>
      </div>
      <div className="terms__item">
        <dt>Ставка, годовых</dt>
        <dd>{percent(terms.rate)}</dd>
      </div>
      <div className="terms__item terms__item--accent">
        <dt>Платёж в месяц</dt>
        <dd>{money(terms.monthly_payment)}</dd>
      </div>
    </dl>
  );
}

/** Requested vs offered terms; the payment shows why the bank changed them. */
function OfferCompare({ summary, terms }: { summary: ApplicationSummary; terms: LoanTerms }) {
  const sameProduct = summary.product_id === terms.product_id;
  const requestedPayment =
    sameProduct && summary.amount !== null && summary.term_months !== null
      ? annuityPayment(summary.amount, terms.rate, summary.term_months)
      : null;
  return (
    <div className="table-wrap">
      <table className="compare">
        <thead>
          <tr>
            <th />
            <th>Вы запросили</th>
            <th>Предложение банка</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>Продукт</th>
            <td>{PRODUCT_NAMES[summary.product_id]}</td>
            <td>{PRODUCT_NAMES[terms.product_id]}</td>
          </tr>
          <tr>
            <th>Сумма</th>
            <td>{money(summary.amount)}</td>
            <td>
              <strong>{money(terms.amount)}</strong>
            </td>
          </tr>
          <tr>
            <th>Срок</th>
            <td>{months(summary.term_months)}</td>
            <td>
              <strong>{months(terms.term_months)}</strong>
            </td>
          </tr>
          <tr>
            <th>Ставка</th>
            <td>{sameProduct ? `${percent(terms.rate)} годовых` : "—"}</td>
            <td>{percent(terms.rate)} годовых</td>
          </tr>
          <tr>
            <th>Платёж в месяц</th>
            <td>{requestedPayment !== null ? `≈ ${money(requestedPayment)}` : "—"}</td>
            <td>
              <strong>{money(terms.monthly_payment)}</strong>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

const ANSWER_FIELDS = ["revenue_year", "expenses_year", "liabilities_total", "amount", "term_months"] as const;
type AnswerField = (typeof ANSWER_FIELDS)[number];

function ClarificationForm({
  detail,
  onChanged,
}: {
  detail: ApplicationDetail;
  onChanged: (detail: ApplicationDetail) => void;
}) {
  const requested = detail.clarification?.requested_fields ?? [];
  const fields = ANSWER_FIELDS.filter((f) => requested.includes(f));
  const [values, setValues] = useState<Partial<Record<AnswerField, string>>>({});
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const answer: ClarificationAnswer = {};
    for (const field of fields) {
      const value = parseInteger(values[field] ?? "");
      if (value === null) {
        setError(`Заполните поле «${FIELD_LABELS[field]}» цифрами.`);
        return;
      }
      answer[field] = value;
    }
    if (fields.length === 0 && !comment.trim()) {
      setError("Напишите ответ на вопрос банка.");
      return;
    }
    if (comment.trim()) answer.clarification_answer = comment.trim();
    setBusy(true);
    setError("");
    try {
      onChanged(await api.answerClarification(detail.id, answer));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel panel--warning" onSubmit={handleSubmit} noValidate>
      <h4>Банку нужны уточнения</h4>
      {detail.clarification && <p>{detail.clarification.message}</p>}
      {fields.map((field) => (
        <label key={field}>
          {FIELD_LABELS[field]}
          <input
            inputMode="numeric"
            value={values[field] ?? ""}
            onChange={(e) => setValues((current) => ({ ...current, [field]: groupDigits(e.target.value) }))}
          />
        </label>
      ))}
      <label>
        Комментарий для банка{fields.length > 0 ? " (необязательно)" : ""}
        <textarea
          maxLength={2000}
          value={comment}
          placeholder="Например: выручка по данным бухгалтерии за последние 12 месяцев"
          onChange={(e) => setComment(e.target.value)}
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="button button--primary" disabled={busy}>
          {busy ? "Отправляем…" : "Отправить ответ"}
        </button>
      </div>
    </form>
  );
}

export default function ApplicationCard({ summary, detail, highlighted, onChanged, onEdit }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  // The version of the agreement the client confirmed reading: a new version needs a new tick.
  const [agreedTo, setAgreedTo] = useState<string | null>(null);
  const [proposing, setProposing] = useState(false);
  const [submitKey] = useState(newIdempotencyKey);

  const actions = detail?.available_actions ?? [];
  const decision = detail?.decision ?? null;
  const terms = decision?.terms ?? null;
  const working = IN_PROGRESS.includes(summary.status) || Boolean(detail?.waiting_external);

  async function run(name: string, action: () => Promise<ApplicationDetail>, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(name);
    setError("");
    try {
      onChanged(await action());
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  const negotiation = detail?.negotiation ?? null;
  const negotiated = (negotiation?.proposals.length ?? 0) > 0;
  const latestVersion = negotiation?.versions[negotiation.versions.length - 1] ?? null;
  const waitingAnswer = summary.status === "manual_review" && Boolean(negotiation?.proposals.some((p) => !p.answered));
  const agreements = detail?.agreements ?? [];
  const agreement = agreements[agreements.length - 1] ?? null;
  const agreementKey = agreement?.sha256 ?? "terms";
  const agreed = agreedTo === agreementKey;

  /** Signs the version of the agreement on the screen; a newer one is shown instead of signed. */
  async function signAgreement() {
    setBusy("sign");
    setError("");
    try {
      onChanged(await api.sign(summary.id, agreement?.sha256));
    } catch (caught) {
      setError(errorText(caught));
      if (caught instanceof ApiError && caught.status === 409) {
        setAgreedTo(null);
        try {
          onChanged(await api.application(summary.id));
        } catch {
          // The message above is enough; the card refreshes on the next poll.
        }
      }
    } finally {
      setBusy(null);
    }
  }

  const requested =
    summary.amount !== null && summary.term_months !== null
      ? `${money(summary.amount)} на ${months(summary.term_months)}`
      : "сумма и срок не указаны";

  return (
    <article id={`application-${summary.id}`} className={`application-card${highlighted ? " application-card--highlight" : ""}`}>
      <header className="application-card__header">
        <div>
          <h3>{PRODUCT_NAMES[summary.product_id]}</h3>
          <p className="application-card__terms">{requested}</p>
        </div>
        <StatusBadge application={summary} />
      </header>

      <Progress status={summary.status} />

      {detail && (
        <div className={`next-step${working ? " next-step--working" : ""}`}>
          {working ? (
            <span className="spinner" aria-hidden="true" />
          ) : (
            <svg
              className="next-step__icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4" />
              <path d="M12 8h.01" />
            </svg>
          )}
          <div>
            <span className="next-step__label">
              {working ? "Сейчас" : summary.client_stage === "completed" ? "Итог" : "Что дальше"}
            </span>
            <p className="next-step__text">{detail.next_step}</p>
          </div>
        </div>
      )}

      {detail && actions.includes("answer_clarification") && (
        <ClarificationForm detail={detail} onChanged={onChanged} />
      )}

      {detail && (actions.includes("accept") || actions.includes("decline")) && terms && (
        <div className="panel panel--success">
          <h4>
            {latestVersion?.in_reply_to
              ? `Банк ответил на ваши условия — версия ${latestVersion.version}`
              : summary.status === "counter_offer"
                ? "Банк предлагает другие условия"
                : "Условия банка"}
          </h4>
          {negotiated ? (
            <>
              {decision?.reason && <p>{decision.reason}</p>}
              <TermsList terms={terms} showProduct={terms.product_id !== summary.product_id} />
              {negotiation && <NegotiationPanel negotiation={negotiation} viewer="client" heading />}
            </>
          ) : summary.status === "counter_offer" ? (
            <>
              {decision?.reason && <p>{decision.reason}</p>}
              <OfferCompare summary={summary} terms={terms} />
            </>
          ) : (
            <TermsList terms={terms} showProduct={terms.product_id !== summary.product_id} />
          )}
          <CashPlanSection detail={detail} onChanged={onChanged} />
          {detail.schedule && <PaymentScheduleView schedule={detail.schedule} />}
          {proposing && (
            <ProposalForm
              detail={detail}
              terms={terms}
              onCancel={() => setProposing(false)}
              onSent={(updated) => {
                setProposing(false);
                onChanged(updated);
              }}
            />
          )}
          <div className="actions">
            <button
              type="button"
              className="button button--primary"
              disabled={busy !== null}
              onClick={() => void run("accept", () => api.respondToOffer(summary.id, true))}
            >
              {busy === "accept" ? "Принимаем…" : "Принять условия"}
            </button>
            {actions.includes("propose") && !proposing && (
              <button
                type="button"
                className="button button--secondary"
                disabled={busy !== null}
                onClick={() => setProposing(true)}
              >
                Предложить свои условия
              </button>
            )}
            <button
              type="button"
              className="button button--secondary"
              disabled={busy !== null}
              onClick={() =>
                void run(
                  "decline",
                  () => api.respondToOffer(summary.id, false),
                  "Отказаться от предложения? Заявка будет закрыта.",
                )
              }
            >
              Отказаться
            </button>
          </div>
        </div>
      )}

      {detail && waitingAnswer && negotiation && (
        <div className="panel">
          <h4>Ваши условия у банка</h4>
          <NegotiationPanel negotiation={negotiation} viewer="client" />
        </div>
      )}

      {detail && actions.includes("sign") && (
        <div className="panel panel--accent">
          <h4>Подписание документов</h4>
          {terms && <TermsList terms={terms} showProduct={terms.product_id !== summary.product_id} />}
          <CashPlanSection detail={detail} onChanged={onChanged} />
          {detail.schedule && <PaymentScheduleView schedule={detail.schedule} open />}
          {agreement && <AgreementPanel key={agreement.sha256} applicationId={summary.id} agreements={agreements} />}
          <label className="checkbox">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreedTo(e.target.checked ? agreementKey : null)}
            />
            {agreement
              ? `Я ознакомился с договором № ${agreement.number} (редакция ${agreement.version}) и графиком платежей`
              : "Я ознакомился с условиями кредитного договора и графиком платежей"}
          </label>
          <p className="muted small">Подписание смоделировано: электронная подпись и перевод денег не выполняются.</p>
          <div className="actions">
            <button
              type="button"
              className="button button--primary"
              disabled={!agreed || busy !== null}
              onClick={() => void signAgreement()}
            >
              {busy === "sign" ? "Подписываем…" : "Подписать и получить деньги"}
            </button>
          </div>
        </div>
      )}

      {detail && summary.status === "rejected" && decision && (
        <div className="panel panel--danger">
          <h4>Причина отказа</h4>
          <p>{decision.reason}</p>
          {decision.comment && <p>{decision.comment}</p>}
        </div>
      )}

      {detail && summary.status === "issued" && terms && (
        <div className="panel panel--success">
          <h4>Кредит выдан</h4>
          <TermsList terms={terms} showProduct={terms.product_id !== summary.product_id} />
          {detail.schedule && <PaymentScheduleView schedule={detail.schedule} issued />}
          {agreement && <AgreementPanel key={agreement.sha256} applicationId={summary.id} agreements={agreements} />}
        </div>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <div className="actions">
        {detail && actions.includes("submit") && (
          <button
            type="button"
            className="button button--primary"
            disabled={busy !== null}
            onClick={() => void run("submit", () => api.submit(summary.id, submitKey))}
          >
            {busy === "submit" ? "Отправляем…" : "Отправить в банк"}
          </button>
        )}
        {detail && actions.includes("edit") && (
          <button type="button" className="button button--secondary" onClick={() => onEdit(detail)}>
            Редактировать
          </button>
        )}
        {detail && actions.includes("withdraw") && (
          <button
            type="button"
            className="button button--ghost"
            disabled={busy !== null}
            onClick={() =>
              void run(
                "withdraw",
                () => api.withdraw(summary.id),
                summary.status === "draft" ? "Удалить черновик?" : "Отозвать заявку? Её нельзя будет вернуть.",
              )
            }
          >
            {summary.status === "draft" ? "Удалить черновик" : "Отозвать заявку"}
          </button>
        )}
        <button type="button" className="link-button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
          {expanded ? "Скрыть подробности" : "Подробнее"}
        </button>
      </div>

      {expanded && detail && (
        <div className="application-card__details">
          <dl className="facts">
            <dt>Номер заявки</dt>
            <dd className="mono">{detail.id}</dd>
            <dt>Компания</dt>
            <dd>
              {detail.company.name}, ИНН {detail.company.inn}
            </dd>
            {detail.purpose_category && (
              <>
                <dt>Цель</dt>
                <dd>
                  {PURPOSE_LABELS[detail.purpose_category]}
                  {detail.purpose ? `: ${detail.purpose}` : ""}
                </dd>
              </>
            )}
            <dt>Создана</dt>
            <dd>{dateTime(detail.created_at)}</dd>
            {detail.submitted_at && (
              <>
                <dt>Отправлена</dt>
                <dd>{dateTime(detail.submitted_at)}</dd>
              </>
            )}
          </dl>
          <h4>История</h4>
          <Timeline history={detail.history} />
        </div>
      )}
    </article>
  );
}
