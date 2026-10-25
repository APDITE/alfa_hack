import { useCallback, useEffect, useState, type FormEvent } from "react";

import { api, errorText } from "../api/client";
import type {
  ApplicationDetail,
  DecisionOutcome,
  LoanTerms,
  ManualDecision,
  Product,
  ProductId,
  Proposal,
} from "../api/types";
import { annuityPayment, date, dateTime, groupDigits, money, months, parseInteger, percent } from "../utils/format";
import { usePolling } from "../utils/hooks";
import {
  ACTOR_LABELS,
  CHECK_LABELS,
  CHECK_OUTCOME_LABELS,
  FACTOR_LABELS,
  FIELD_LABELS,
  OUTCOME_LABELS,
  PRODUCT_NAMES,
  PURPOSE_LABELS,
  RISK_LABELS,
  RULE_LABELS,
} from "../utils/labels";
import { cashPlanSummary } from "../utils/cash";
import AgreementPanel from "./AgreementPanel";
import { NegotiationPanel } from "./Negotiation";
import StatusBadge from "./StatusBadge";
import Timeline from "./Timeline";

type Props = {
  id: string;
  products: Product[];
  onBack: () => void;
  onDecided: () => void;
};

const OUTCOMES: { id: DecisionOutcome; label: string }[] = [
  { id: "approved", label: "Одобрить" },
  { id: "counter_offer", label: "Другие условия" },
  { id: "clarification", label: "Запросить данные" },
  { id: "rejected", label: "Отказать" },
];

const CHECK_TONE: Record<string, string> = {
  passed: "success",
  failed: "danger",
  pending: "info",
  unavailable: "warning",
};

const rateInput = (rate: number | null) => (rate !== null ? String(rate).replace(".", ",") : "");

function DecisionForm({
  detail,
  products,
  proposal,
  previous,
  onDone,
}: {
  detail: ApplicationDetail;
  products: Product[];
  /** The client's terms waiting for an answer, if the client is negotiating. */
  proposal: Proposal | null;
  /** The bank's latest offer, to keep it in a negotiation. */
  previous: { version: number; terms: LoanTerms } | null;
  onDone: (detail: ApplicationDetail) => void;
}) {
  const [outcome, setOutcome] = useState<DecisionOutcome>("approved");
  const [comment, setComment] = useState("");
  const [fields, setFields] = useState<string[]>([]);
  const [productId, setProductId] = useState<ProductId>(detail.product_id);
  const [amountText, setAmountText] = useState(detail.amount ? groupDigits(String(detail.amount)) : "");
  const [termText, setTermText] = useState(detail.term_months ? String(detail.term_months) : "");
  const [rateText, setRateText] = useState(rateInput(proposal?.rate ?? null));

  function fill(terms: { product_id?: ProductId; amount: number; term_months: number; rate: number | null }) {
    setOutcome("counter_offer");
    if (terms.product_id) setProductId(terms.product_id);
    setAmountText(groupDigits(String(terms.amount)));
    setTermText(String(terms.term_months));
    setRateText(rateInput(terms.rate));
  }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const product = products.find((p) => p.id === productId);
  const amount = parseInteger(amountText);
  const term = parseInteger(termText);
  const rate = rateText ? Number(rateText.replace(",", ".")) : null;
  const previewRate = rate ?? product?.base_rate ?? null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!comment.trim()) {
      setError("Напишите комментарий: он попадёт в историю заявки.");
      return;
    }
    const body: ManualDecision = { outcome, comment: comment.trim() };
    if (outcome === "clarification") {
      if (fields.length === 0) {
        setError("Отметьте, какие данные нужны от клиента.");
        return;
      }
      body.requested_fields = fields;
    }
    if (outcome === "counter_offer") {
      if (!product || amount === null || term === null) {
        setError("Укажите продукт, сумму и срок предложения.");
        return;
      }
      if (amount < product.min_amount || amount > product.max_amount) {
        setError(`Сумма: от ${money(product.min_amount)} до ${money(product.max_amount)}.`);
        return;
      }
      if (term < product.min_term_months || term > product.max_term_months) {
        setError(`Срок: от ${product.min_term_months} до ${product.max_term_months} мес.`);
        return;
      }
      if (rate !== null && !(rate > 0 && rate < 100)) {
        setError("Ставка — число от 0 до 100.");
        return;
      }
      body.terms = { product_id: product.id, amount, term_months: term, rate };
    }
    const confirmText = {
      approved: proposal
        ? `Принять условия клиента: ${money(proposal.amount)} на ${months(proposal.term_months)}${
            proposal.rate !== null ? `, ставка ${percent(proposal.rate)}` : ""
          }?`
        : "Одобрить заявку на запрошенных условиях?",
      counter_offer: "Отправить клиенту предложение на других условиях?",
      clarification: "Запросить у клиента недостающие данные?",
      rejected: "Отказать по заявке?",
    }[outcome];
    if (!window.confirm(confirmText)) return;

    setBusy(true);
    setError("");
    try {
      onDone(await api.decide(detail.id, body));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card decision-form" onSubmit={handleSubmit} noValidate>
      <h3>{proposal ? `Ответ на условия клиента, раунд ${proposal.round}` : "Решение по заявке"}</h3>
      <div className="segmented" role="radiogroup" aria-label="Решение">
        {OUTCOMES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={outcome === item.id}
            className={`segmented__item segmented__item--${item.id}${outcome === item.id ? " is-active" : ""}`}
            onClick={() => setOutcome(item.id)}
          >
            {proposal && item.id === "approved" ? "Принять условия клиента" : item.label}
          </button>
        ))}
      </div>
      {proposal && (
        <div className="decision-form__prefill">
          <span className="muted small">
            «Принять» — одобрить сумму и срок клиента
            {proposal.rate !== null ? ` по его ставке ${percent(proposal.rate)}` : " по ставке с надбавкой за риск"}.
            Подставить в «Другие условия»:
          </span>
          <button
            type="button"
            className="button button--secondary button--small"
            onClick={() => fill({ amount: proposal.amount, term_months: proposal.term_months, rate: proposal.rate })}
          >
            Условия клиента
          </button>
          {previous && (
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={() => fill(previous.terms)}
            >
              Прежнее предложение, версия {previous.version}
            </button>
          )}
        </div>
      )}

      {outcome === "counter_offer" && (
        <div className="counter-offer">
          <label>
            Продукт
            <select value={productId} onChange={(e) => setProductId(e.target.value as ProductId)}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
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
              Ставка, %
              <input
                inputMode="decimal"
                value={rateText}
                placeholder={product ? `${product.base_rate} + надбавка` : ""}
                onChange={(e) => setRateText(e.target.value.replace(/[^\d.,]/g, ""))}
              />
            </label>
          </div>
          {product && amount !== null && term !== null && previewRate !== null && term > 0 && (
            <p className="muted small">
              Платёж ≈ {money(annuityPayment(amount, previewRate, term))} в месяц
              {rate === null ? ` по базовой ставке ${percent(product.base_rate)}; банк добавит надбавку за риск` : ""}.
            </p>
          )}
        </div>
      )}

      {outcome === "clarification" && (
        <fieldset className="fields">
          <legend>Что запросить у клиента</legend>
          {Object.entries(FIELD_LABELS).map(([field, label]) => (
            <label key={field} className="checkbox">
              <input
                type="checkbox"
                checked={fields.includes(field)}
                onChange={() =>
                  setFields((current) =>
                    current.includes(field) ? current.filter((f) => f !== field) : [...current, field],
                  )
                }
              />
              {label}
            </label>
          ))}
        </fieldset>
      )}

      <label>
        {outcome === "clarification" ? "Вопрос клиенту (он увидит этот текст)" : "Комментарий к решению"}
        <textarea
          maxLength={2000}
          value={comment}
          placeholder={
            outcome === "clarification"
              ? "Например: подтвердите выручку за последние 12 месяцев"
              : "Почему принято такое решение"
          }
          onChange={(e) => setComment(e.target.value)}
        />
      </label>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" className={`button button--primary button--${outcome}`} disabled={busy}>
        {busy ? "Сохраняем…" : OUTCOMES.find((o) => o.id === outcome)?.label}
      </button>
    </form>
  );
}

export default function BankApplication({ id, products, onBack, onDecided }: Props) {
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    try {
      setDetail(await api.application(id));
      setError("");
    } catch (caught) {
      setError(errorText(caught));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);
  usePolling(load, 4000);

  if (!detail) {
    return (
      <section className="card">
        <button type="button" className="link-button" onClick={onBack}>
          ← К очереди
        </button>
        <p className={error ? "form-error" : "muted"}>{error || "Загружаем заявку…"}</p>
      </section>
    );
  }

  const canDecide = detail.available_actions.includes("decide");
  const { company, score, decision, negotiation } = detail;
  const openProposal = negotiation?.proposals.find((p) => !p.answered) ?? null;
  const lastVersion = negotiation?.versions[negotiation.versions.length - 1] ?? null;
  const agreement = detail.agreements[detail.agreements.length - 1] ?? null;
  const clientFinancials = detail.revenue_year !== null || detail.expenses_year !== null || detail.liabilities_total !== null;

  return (
    <section className="bank-application">
      <button type="button" className="link-button" onClick={onBack}>
        ← К очереди
      </button>

      <header className="bank-application__header">
        <div>
          <h2>{company.name}</h2>
          <p className="muted">
            {PRODUCT_NAMES[detail.product_id]} · {money(detail.amount)} на {months(detail.term_months)}
          </p>
        </div>
        <div className="badges">
          {score && <span className={`badge badge--risk-${score.risk_class}`}>{RISK_LABELS[score.risk_class]}</span>}
          <StatusBadge application={detail} tone={detail.status === "manual_review" ? "warning" : undefined} />
        </div>
      </header>

      {saved && (
        <p className="notice" role="status">
          {saved}
        </p>
      )}
      {error && <p className="form-error">{error}</p>}

      <div className="bank-grid">
        <div className="bank-grid__column">
          <div className="card">
            <h3>Заявка и компания</h3>
            <dl className="facts">
              <dt>Цель</dt>
              <dd>
                {detail.purpose_category ? PURPOSE_LABELS[detail.purpose_category] : "—"}
                {detail.purpose ? `: ${detail.purpose}` : ""}
              </dd>
              <dt>ИНН</dt>
              <dd>{company.inn}</dd>
              <dt>ОКВЭД</dt>
              <dd>{company.okved}</dd>
              <dt>Регистрация</dt>
              <dd>{date(company.registration_date)}</dd>
              <dt>Руководитель</dt>
              <dd>{company.director}</dd>
              {detail.submitted_at && (
                <>
                  <dt>Подана</dt>
                  <dd>{dateTime(detail.submitted_at)}</dd>
                </>
              )}
            </dl>
            {clientFinancials && (
              <>
                <h4>Данные, введённые клиентом</h4>
                <dl className="facts">
                  <dt>Выручка</dt>
                  <dd>{money(detail.revenue_year)}</dd>
                  <dt>Расходы</dt>
                  <dd>{money(detail.expenses_year)}</dd>
                  <dt>Долги</dt>
                  <dd>{money(detail.liabilities_total)}</dd>
                </dl>
              </>
            )}
            {detail.clarification?.answer && (
              <p className="quote">Ответ клиента: {detail.clarification.answer}</p>
            )}
          </div>

          <div className="card">
            <h3>Проверки</h3>
            {detail.checks.length === 0 ? (
              <p className="muted">Проверок пока нет.</p>
            ) : (
              <ul className="checks">
                {detail.checks.map((check, index) => (
                  <li key={`${check.type}-${index}`}>
                    <span className={`dot dot--${CHECK_TONE[check.outcome] ?? "info"}`} aria-hidden="true" />
                    <div>
                      <strong>{CHECK_LABELS[check.type]}</strong> — {CHECK_OUTCOME_LABELS[check.outcome]}
                      <div className="muted small">{check.summary}</div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h3>История и аудит</h3>
            <Timeline history={detail.history} audit />
          </div>
        </div>

        <div className="bank-grid__column">
          <div className="card">
            <h3>Оценка риска</h3>
            {score ? (
              <>
                <div className="score">
                  <div>
                    <div className="score__value">{percent(Math.round(score.score * 1000) / 10)}</div>
                    <div className="muted small">вероятность дефолта</div>
                  </div>
                  <div>
                    <div className="score__value">{score.points_total}</div>
                    <div className="muted small">баллов, {score.model_version}</div>
                  </div>
                </div>
                <ul className="factors">
                  {score.factors.map((factor) => (
                    <li key={factor.name} className={`factor factor--${factor.impact}`}>
                      <span className="factor__points">
                        {factor.points > 0 ? "+" : ""}
                        {factor.points}
                      </span>
                      <span>
                        <strong>{FACTOR_LABELS[factor.name] ?? factor.name}</strong>: {factor.comment}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="muted">Оценки нет: заявка остановилась до скоринга или сервис был недоступен.</p>
            )}
          </div>

          {negotiation && negotiation.proposals.length > 0 && (
            <div className={`card${openProposal && canDecide ? " card--attention" : ""}`}>
              <h3>{openProposal && canDecide ? "Клиент предлагает свои условия" : "Переговоры"}</h3>
              <NegotiationPanel negotiation={negotiation} viewer="bank" />
            </div>
          )}

          {agreement && (
            <div className="card">
              <h3>Кредитный договор</h3>
              <AgreementPanel key={agreement.sha256} applicationId={detail.id} agreements={detail.agreements} />
            </div>
          )}

          {detail.cash_plan && (
            <div className="card">
              <h3>Денежный календарь клиента</h3>
              <p>
                <strong>Платёж {detail.cash_plan.payment_day}-го числа</strong>: {cashPlanSummary(detail.cash_plan)}.
              </p>
              <dl className="facts">
                <dt>Остаток на 1-е</dt>
                <dd>{money(detail.cash_plan.calendar.opening_balance)}</dd>
                <dt>Поступления</dt>
                <dd>
                  {money(
                    detail.cash_plan.calendar.events
                      .filter((e) => e.amount > 0)
                      .reduce((sum, e) => sum + e.amount, 0),
                  )}{" "}
                  в месяц
                </dd>
                <dt>Расходы</dt>
                <dd>
                  {money(
                    -detail.cash_plan.calendar.events
                      .filter((e) => e.amount < 0)
                      .reduce((sum, e) => sum + e.amount, 0),
                  )}{" "}
                  в месяц
                </dd>
              </dl>
            </div>
          )}

          {decision && (
            <div className="card">
              <h3>Последнее решение</h3>
              <dl className="facts">
                <dt>Итог</dt>
                <dd>{OUTCOME_LABELS[decision.outcome]}</dd>
                <dt>Правило</dt>
                <dd>
                  {RULE_LABELS[decision.rule] ?? decision.rule} <code>{decision.rule}</code>
                </dd>
                <dt>Кто решил</dt>
                <dd>
                  {ACTOR_LABELS[decision.decided_by]}, {dateTime(decision.decided_at)}
                </dd>
                {decision.terms && (
                  <>
                    <dt>Условия</dt>
                    <dd>
                      {PRODUCT_NAMES[decision.terms.product_id]}, {money(decision.terms.amount)} на{" "}
                      {months(decision.terms.term_months)}, {percent(decision.terms.rate)}, платёж{" "}
                      {money(decision.terms.monthly_payment)}
                    </dd>
                  </>
                )}
                {decision.comment && (
                  <>
                    <dt>Комментарий</dt>
                    <dd>{decision.comment}</dd>
                  </>
                )}
              </dl>
            </div>
          )}

          {canDecide ? (
            <DecisionForm
              key={openProposal ? `round-${openProposal.round}` : "decision"}
              detail={detail}
              products={products}
              proposal={openProposal}
              previous={lastVersion}
              onDone={(updated) => {
                setDetail(updated);
                setSaved(`Решение сохранено: ${updated.status_label}. Клиент увидит его в кабинете.`);
                onDecided();
              }}
            />
          ) : (
            <div className="card">
              <p className="muted">
                {detail.status === "manual_review"
                  ? "Решение недоступно."
                  : "Сотрудник принимает решение только по заявкам на ручной проверке."}{" "}
                Следующий шаг: {detail.next_step}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
