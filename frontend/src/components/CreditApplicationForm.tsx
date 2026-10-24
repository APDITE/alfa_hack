
import { useState, type FormEvent } from "react";
import type { CreditApplication } from "../types/application";
import {
  createApplication,
  updateApplication,
  type ProductId,
} from "../api/applications";

type CreditApplicationFormProps = {
  productId: ProductId;
  productName: string;
  onClose: () => void;
  application?: CreditApplication;
};

export default function CreditApplicationForm({
  productId,
  productName,
  onClose,
  application,
}: CreditApplicationFormProps) {
  const [amount, setAmount] = useState(
    application?.amount.toString() ?? ""
  );
  const [term, setTerm] = useState(
    application?.term.toString() ?? ""
  );
  const [purpose, setPurpose] = useState(
    application?.purpose ?? ""
  );

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const amountValue = Number(amount);
    const termValue = Number(term);

    if (
      !Number.isSafeInteger(amountValue) ||
      amountValue <= 0 ||
      !Number.isSafeInteger(termValue) ||
      termValue <= 0
    ) {
      setError("Введите корректную сумму и срок кредита.");
      return;
    }

    if (!purpose.trim()) {
      setError("Укажите цель кредитования.");
      return;
    }

    if (purpose.trim().length > 500) {
      setError("Цель кредитования не должна превышать 500 символов.");
      return;
    }

    setSaving(true);

    try {
      const data = {
        product_id: productId,
        purpose_category: productId === "equipment"
          ? ("equipment" as const)
          : ("other" as const),
        amount: amountValue,
        term_months: termValue,
        purpose: purpose.trim(),
      };

      if (application) {
        if (application.status !== "draft") {
          throw new Error("Редактировать можно только черновик.");
        }

        await updateApplication(application.id, data);
      } else {
        await createApplication(data);
      }

      setSaved(true);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Не удалось сохранить черновик."
      );
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <section className="application-form">
        <h2>Черновик заявки сохранён</h2>
        <p>
          Черновик успешно сохранён на сервере банка.
          Заявка пока не отправлена на рассмотрение.
        </p>
        <button type="button" onClick={onClose}>
          Вернуться к кредитным продуктам
        </button>
      </section>
    );
  }

  return (
    <section className="application-form">
      <h2>Оформление кредитной заявки</h2>
      <p>Продукт: {productName}</p>

      <form onSubmit={handleSubmit}>
        <label>
          Сумма кредита, ₽
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]+"
            title="Введите сумму кредита"
            required
            value={amount}
            onChange={(event) => {
              const value = event.target.value;
              if (/^\d*$/.test(value)) {
                setAmount(value);
              }
            }}
            placeholder="Например, 1000000"
          />
        </label>

        <label>
          Срок кредита, месяцев
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]+"
            title="Введите срок целым положительным числом"
            required
            value={term}
            onChange={(event) => {
              const value = event.target.value;
              if (/^\d*$/.test(value)) {
                setTerm(value);
              }
            }}
            placeholder="Например, 12"
          />
        </label>

        <label>
          Цель кредитования
          <textarea
            required
            maxLength={500}
            value={purpose}
            onChange={(event) => setPurpose(event.target.value)}
            placeholder="На что планируете потратить кредит?"
          />
        </label>

        <p>
          Данные компании будут определены автоматически
          по вашей учётной записи.
        </p>

        {error && (
          <p role="alert" style={{ color: "#c62828" }}>
            {error}
          </p>
        )}

        <div className="application-actions">
          <button type="button" onClick={onClose} disabled={saving}>
            Отмена
          </button>

          <button type="submit" disabled={saving}>
            {saving ? "Сохранение..." : "Сохранить черновик"}
          </button>
        </div>
      </form>
    </section>
  );
}
