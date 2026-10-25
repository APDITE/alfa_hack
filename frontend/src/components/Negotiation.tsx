import { useMemo, useState, type FormEvent } from "react";

import { api, errorText } from "../api/client";
import type { ApplicationDetail, LoanTerms, Negotiation, ProposalInput } from "../api/types";
import { annuityPayment, dateTime, groupDigits, money, parseInteger, percent, plural } from "../utils/format";

/** One step of the negotiation in the same shape, for the list and the comparison. */
type Step = {
  key: string;
  side: "bank" | "client";
  title: string;
  at: string;
  amount: number;
  term: number;
  rate: number | null;
  payment: number;
  /** Exact for the bank's versions, approximate for the client's proposals. */
  overpayment: number;
  exact: boolean;
  wish: string | null;
  pending: boolean;
};

function steps(negotiation: Negotiation): Step[] {
  const all: Step[] = [
    ...negotiation.versions.map(
      (v): Step => ({
        key: `v${v.version}`,
        side: "bank",
        title: `Банк, версия ${v.version}`,
        at: v.created_at,
        amount: v.terms.amount,
        term: v.terms.term_months,
        rate: v.terms.rate,
        payment: v.terms.monthly_payment,
        overpayment: v.total_interest,
        exact: true,
        wish: null,
        pending: false,
      }),
    ),
    ...negotiation.proposals.map(
      (p): Step => ({
        key: `r${p.round}`,
        side: "client",
        title: `Клиент, раунд ${p.round}`,
        at: p.created_at,
        amount: p.amount,
        term: p.term_months,
        rate: p.rate,
        payment: p.monthly_payment,
        overpayment: p.monthly_payment * p.term_months - p.amount,
        exact: false,
        wish: p.comment,
        pending: !p.answered,
      }),
    ),
  ];
  return all.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
}

function signed(value: number, format: (v: number) => string): string {
  if (value === 0) return "—";
  return `${value > 0 ? "+" : "−"}${format(Math.abs(value))}`;
}

function termsLine(step: Step): string {
  const rate = step.rate !== null ? percent(step.rate) : "ставка банка";
  return `${money(step.amount)} · ${step.term} мес. · ${rate} · ${money(step.payment)} в месяц`;
}

type PanelProps = {
  negotiation: Negotiation;
  viewer: "client" | "bank";
  /** Own heading; off where the surrounding card already has one. */
  heading?: boolean;
};

/** Rounds of the negotiation and a comparison of any two of them. */
export function NegotiationPanel({ negotiation, viewer, heading = false }: PanelProps) {
  const all = useMemo(() => steps(negotiation), [negotiation]);
  const defaultA = all.length > 1 ? all[all.length - 2].key : all[0]?.key;
  const defaultB = all[all.length - 1]?.key;
  const [aKey, setAKey] = useState<string | undefined>(undefined);
  const [bKey, setBKey] = useState<string | undefined>(undefined);
  const a = all.find((s) => s.key === (aKey ?? defaultA));
  const b = all.find((s) => s.key === (bKey ?? defaultB));
  const label = (step: Step) =>
    viewer === "client" && step.side === "client" ? step.title.replace("Клиент", "Вы") : step.title;
  const used = negotiation.proposals.length;

  return (
    <section className="negotiation" aria-label="Переговоры">
      <div className="negotiation__head">
        {heading && <h5>Переговоры</h5>}
        <span className="muted small">
          {used === 0
            ? `Можно предложить свои условия: до ${negotiation.max_rounds} ${plural(negotiation.max_rounds, ["раунда", "раундов", "раундов"])}`
            : `Раунд ${used} из ${negotiation.max_rounds}`}
        </span>
      </div>
      <ol className="negotiation__steps">
        {all.map((step) => (
          <li key={step.key} className={`negotiation__step negotiation__step--${step.side}`}>
            <div className="negotiation__who">
              <strong>{label(step)}</strong>
              <time className="muted small" dateTime={step.at}>
                {dateTime(step.at)}
              </time>
              {step.pending && <span className="badge badge--warning">ждёт ответа банка</span>}
            </div>
            <div className="negotiation__terms">{termsLine(step)}</div>
            {step.wish && <p className="negotiation__wish">«{step.wish}»</p>}
          </li>
        ))}
      </ol>

      {all.length > 1 && a && b && (
        <div className="negotiation__compare">
          <div className="negotiation__pick">
            <label>
              Сравнить
              <select value={a.key} onChange={(e) => setAKey(e.target.value)}>
                {all.map((s) => (
                  <option key={s.key} value={s.key}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              с
              <select value={b.key} onChange={(e) => setBKey(e.target.value)}>
                {all.map((s) => (
                  <option key={s.key} value={s.key}>
                    {label(s)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table className="compare negotiation__table">
              <thead>
                <tr>
                  <th />
                  <th scope="col">{label(a)}</th>
                  <th scope="col">{label(b)}</th>
                  <th scope="col">Разница</th>
                </tr>
              </thead>
              <tbody>
                <tr className={a.amount !== b.amount ? "is-changed" : undefined}>
                  <th scope="row">Сумма</th>
                  <td>{money(a.amount)}</td>
                  <td>{money(b.amount)}</td>
                  <td>{signed(b.amount - a.amount, money)}</td>
                </tr>
                <tr className={a.term !== b.term ? "is-changed" : undefined}>
                  <th scope="row">Срок</th>
                  <td>{a.term} мес.</td>
                  <td>{b.term} мес.</td>
                  <td>{signed(b.term - a.term, (v) => `${v} мес.`)}</td>
                </tr>
                <tr className={a.rate !== b.rate ? "is-changed" : undefined}>
                  <th scope="row">Ставка</th>
                  <td>{a.rate !== null ? percent(a.rate) : "как у банка"}</td>
                  <td>{b.rate !== null ? percent(b.rate) : "как у банка"}</td>
                  <td>
                    {a.rate !== null && b.rate !== null
                      ? signed(Math.round((b.rate - a.rate) * 100) / 100, (v) => `${v.toLocaleString("ru-RU")} п. п.`)
                      : "—"}
                  </td>
                </tr>
                <tr className={a.payment !== b.payment ? "is-changed" : undefined}>
                  <th scope="row">Платёж в месяц</th>
                  <td>{money(a.payment)}</td>
                  <td>{money(b.payment)}</td>
                  <td>{signed(b.payment - a.payment, money)}</td>
                </tr>
                <tr className={a.overpayment !== b.overpayment ? "is-changed" : undefined}>
                  <th scope="row">Переплата</th>
                  <td>
                    {a.exact ? "" : "≈ "}
                    {money(a.overpayment)}
                  </td>
                  <td>
                    {b.exact ? "" : "≈ "}
                    {money(b.overpayment)}
                  </td>
                  <td>{signed(b.overpayment - a.overpayment, money)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

/** The client's own terms in answer to the bank's offer. */
export function ProposalForm({
  detail,
  terms,
  onSent,
  onCancel,
}: {
  detail: ApplicationDetail;
  terms: LoanTerms;
  onSent: (detail: ApplicationDetail) => void;
  onCancel: () => void;
}) {
  const [amountText, setAmountText] = useState(groupDigits(String(terms.amount)));
  const [termText, setTermText] = useState(String(terms.term_months));
  const [rateText, setRateText] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const left = detail.negotiation?.rounds_left ?? 0;
  const max = detail.negotiation?.max_rounds ?? 0;

  const amount = parseInteger(amountText);
  const term = parseInteger(termText);
  const rate = rateText ? Number(rateText.replace(",", ".")) : null;
  const previewRate = rate !== null && rate > 0 ? rate : terms.rate;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (amount === null || term === null || term <= 0) {
      setError("Укажите сумму и срок цифрами.");
      return;
    }
    if (rate !== null && !(rate > 0 && rate < 100)) {
      setError("Ставка — число от 0 до 100.");
      return;
    }
    if (!comment.trim()) {
      setError("Напишите, что для вас важно: банк учтёт это при ответе.");
      return;
    }
    const body: ProposalInput = { amount, term_months: term, rate, comment: comment.trim() };
    setBusy(true);
    setError("");
    try {
      onSent(await api.propose(detail.id, body));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="proposal" onSubmit={handleSubmit} noValidate>
      <h5>Ваши условия</h5>
      <p className="muted small">
        Кредитный специалист рассмотрит их и ответит новой версией предложения. Осталось{" "}
        {left} {plural(left, ["раунд", "раунда", "раундов"])} из {max}.
      </p>
      <div className="form-row">
        <label>
          Сумма, ₽
          <input inputMode="numeric" value={amountText} onChange={(e) => setAmountText(groupDigits(e.target.value))} />
        </label>
        <label>
          Срок, мес.
          <input inputMode="numeric" value={termText} onChange={(e) => setTermText(e.target.value.replace(/\D/g, ""))} />
        </label>
        <label>
          Желаемая ставка, %
          <input
            inputMode="decimal"
            value={rateText}
            placeholder={`сейчас ${percent(terms.rate)}`}
            onChange={(e) => setRateText(e.target.value.replace(/[^\d.,]/g, ""))}
          />
        </label>
      </div>
      <label>
        Что для вас важно
        <textarea
          maxLength={1000}
          value={comment}
          placeholder="Например: выручка сезонная, летом платёж должен быть меньше; готовы взять сумму поменьше"
          onChange={(e) => setComment(e.target.value)}
        />
      </label>
      {amount !== null && term !== null && term > 0 && (
        <p className="muted small">
          Платёж ≈ {money(annuityPayment(amount, previewRate, term))} в месяц при ставке {percent(previewRate)}
          {rate === null ? " (как сейчас)" : ""}.
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="button button--primary" disabled={busy}>
          {busy ? "Отправляем…" : "Отправить банку"}
        </button>
        <button type="button" className="button button--secondary" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  );
}
