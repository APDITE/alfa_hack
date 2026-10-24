import { useRef, useState, type FormEvent } from "react";

import { api, errorText } from "../api/client";
import type { ApplicationDetail, Company, Product, PurposeCategory } from "../api/types";
import {
  annuityPayment,
  groupDigits,
  money,
  newIdempotencyKey,
  parseInteger,
  percent,
} from "../utils/format";
import { PURPOSE_LABELS } from "../utils/labels";

type Props = {
  product: Product;
  purpose: PurposeCategory | null;
  company: Company | null;
  /** Edit an existing draft instead of creating a new one. */
  draft?: ApplicationDetail;
  onCancel: () => void;
  onDone: (application: ApplicationDetail, submitted: boolean) => void;
};

type Errors = Partial<Record<"amount" | "term" | "purpose", string>>;

export default function CreditApplicationForm({
  product,
  purpose,
  company,
  draft,
  onCancel,
  onDone,
}: Props) {
  const [category, setCategory] = useState<PurposeCategory>(
    draft?.purpose_category ?? purpose ?? product.purposes[0],
  );
  const [amountText, setAmountText] = useState(draft?.amount ? groupDigits(String(draft.amount)) : "");
  const [termText, setTermText] = useState(draft?.term_months ? String(draft.term_months) : "");
  const [purposeText, setPurposeText] = useState(draft?.purpose ?? "");
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState<"draft" | "submit" | null>(null);
  // The draft id survives a failed submit, so a retry does not create a second draft.
  const savedId = useRef<string | null>(draft?.id ?? null);
  // One key per form: a repeated click or a retry after a network error is not a new submit.
  const submitKey = useRef(newIdempotencyKey());

  const amount = parseInteger(amountText);
  const term = parseInteger(termText);
  const amountOk = amount !== null && amount >= product.min_amount && amount <= product.max_amount;
  const termOk = term !== null && term >= product.min_term_months && term <= product.max_term_months;

  function validate(strict: boolean): Errors {
    const found: Errors = {};
    if (amountText && amount === null) found.amount = "Введите сумму цифрами.";
    else if (strict && !amountOk)
      found.amount = `Сумма от ${money(product.min_amount)} до ${money(product.max_amount)}.`;
    if (termText && term === null) found.term = "Введите срок целым числом месяцев.";
    else if (strict && !termOk)
      found.term = `Срок от ${product.min_term_months} до ${product.max_term_months} мес.`;
    if (strict && purposeText.trim().length < 3) found.purpose = "Коротко опишите, на что пойдут деньги.";
    return found;
  }

  async function save(submit: boolean) {
    const found = validate(submit);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length > 0) return;

    setBusy(submit ? "submit" : "draft");
    const input = {
      product_id: product.id,
      purpose_category: category,
      amount: amount ?? undefined,
      term_months: term ?? undefined,
      purpose: purposeText.trim() || undefined,
    };
    try {
      let saved = savedId.current
        ? await api.updateDraft(savedId.current, input)
        : await api.createDraft(input);
      savedId.current = saved.id;
      if (submit) saved = await api.submit(saved.id, submitKey.current);
      onDone(saved, submit);
    } catch (caught) {
      setFormError(errorText(caught));
    } finally {
      setBusy(null);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save(true);
  }

  return (
    <section className="card application-form">
      <button type="button" className="link-button" onClick={onCancel}>
        ← Назад
      </button>
      <h2>{draft ? "Черновик заявки" : "Новая заявка"}</h2>
      <p className="muted">
        {product.name}: {money(product.min_amount)} – {money(product.max_amount)}, срок{" "}
        {product.min_term_months}–{product.max_term_months} мес., ставка от {percent(product.base_rate)}.
      </p>

      {company && (
        <div className="prefill">
          <strong>{company.name}</strong>
          <span>
            ИНН {company.inn} · ОКВЭД {company.okved} · руководитель {company.director}
          </span>
          <span className="muted">Данные компании подставлены из реестра, вводить их не нужно.</span>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <label>
          Цель кредита
          <select value={category} onChange={(e) => setCategory(e.target.value as PurposeCategory)}>
            {product.purposes.map((value) => (
              <option key={value} value={value}>
                {PURPOSE_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <div className="form-row">
          <label>
            Сумма, ₽
            <input
              inputMode="numeric"
              autoComplete="off"
              value={amountText}
              placeholder={groupDigits(String(product.min_amount))}
              aria-invalid={Boolean(errors.amount)}
              onChange={(e) => setAmountText(groupDigits(e.target.value))}
            />
            <small className={errors.amount ? "field-error" : "hint"}>
              {errors.amount ?? `от ${money(product.min_amount)} до ${money(product.max_amount)}`}
            </small>
          </label>

          <label>
            Срок, мес.
            <input
              inputMode="numeric"
              autoComplete="off"
              value={termText}
              placeholder={String(product.min_term_months)}
              aria-invalid={Boolean(errors.term)}
              onChange={(e) => setTermText(e.target.value.replace(/\D/g, ""))}
            />
            <small className={errors.term ? "field-error" : "hint"}>
              {errors.term ?? `от ${product.min_term_months} до ${product.max_term_months} мес.`}
            </small>
          </label>
        </div>

        <label>
          Что планируете сделать с деньгами
          <textarea
            maxLength={500}
            value={purposeText}
            placeholder="Например: закупка товара к новогоднему сезону"
            aria-invalid={Boolean(errors.purpose)}
            onChange={(e) => setPurposeText(e.target.value)}
          />
          {errors.purpose && <small className="field-error">{errors.purpose}</small>}
        </label>

        {amountOk && termOk && amount !== null && term !== null && (
          <div className="estimate" role="status">
            Ориентировочный платёж:{" "}
            <strong>{money(annuityPayment(amount, product.base_rate, term))} в месяц</strong> по ставке
            от {percent(product.base_rate)}. Точные условия банк назовёт после проверки.
          </div>
        )}

        {formError && (
          <p className="form-error" role="alert">
            {formError}
          </p>
        )}

        <div className="actions">
          <button type="submit" className="button button--primary" disabled={busy !== null}>
            {busy === "submit" ? "Отправляем…" : "Отправить в банк"}
          </button>
          <button
            type="button"
            className="button button--secondary"
            disabled={busy !== null}
            onClick={() => void save(false)}
          >
            {busy === "draft" ? "Сохраняем…" : "Сохранить черновик"}
          </button>
          <button type="button" className="button button--ghost" onClick={onCancel} disabled={busy !== null}>
            Отмена
          </button>
        </div>
      </form>
    </section>
  );
}
