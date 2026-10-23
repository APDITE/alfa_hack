
import { useState, type FormEvent } from "react";

type CreditApplicationFormProps = {
  productName: string;
  onClose: () => void;
};

export default function CreditApplicationForm({
  productName,
  onClose,
}: CreditApplicationFormProps) {
  const [amount, setAmount] = useState("");
  const [term, setTerm] = useState("");
  const [purpose, setPurpose] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [inn, setInn] = useState("");
  const [saved, setSaved] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(true);
  }

  if (saved) {
    return (
      <section className="application-form">
        <h2>Черновик заявки заполнен</h2>
        <p>
          Данные прошли проверку формы. Заявка пока не отправлена
          и не сохранена на сервере.
        </p>
        <button type="button" onClick={onClose}>
          Вернуться к продуктам
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
            type="number"
            min="1"
            step="1"
            required
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="Например, 1000000"
          />
        </label>

        <label>
          Срок кредита, месяцев
          <input
            type="number"
            min="1"
            step="1"
            required
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Например, 12"
          />
        </label>

        <label>
          Цель кредитования
          <textarea
            required
            value={purpose}
            onChange={(event) => setPurpose(event.target.value)}
            placeholder="На что планируете потратить кредит?"
          />
        </label>

        <label>
          Название компании
          <input
            type="text"
            required
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            placeholder="ООО Пример"
          />
        </label>

        <label>
          ИНН компании
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]{10}|[0-9]{12}"
            title="ИНН должен содержать 10 или 12 цифр"
            required
            value={inn}
            onChange={(event) => setInn(event.target.value)}
            placeholder="10 или 12 цифр"
          />
        </label>

        <div className="application-actions">
          <button type="button" onClick={onClose}>
            Отмена
          </button>
          <button type="submit">Проверить черновик</button>
        </div>
      </form>
    </section>
  );
}
