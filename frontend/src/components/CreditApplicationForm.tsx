import { useState, type FormEvent } from "react";
import type { CreditApplication } from "../types/application";
import { saveApplication, updateApplication } from "../utils/applicationStorage";

type CreditApplicationFormProps = {
  productName: string;
  onClose: () => void;
  application?: CreditApplication;
};

export default function CreditApplicationForm({
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
    const [companyName, setCompanyName] = useState(
    application?.companyName ?? ""
    );
    const [inn, setInn] = useState(
    application?.inn ?? ""
    );
    const [saved, setSaved] = useState(false);


  

function handleSubmit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  if (
  !Number.isSafeInteger(Number(amount)) ||
  Number(amount) <= 0 ||
  !Number.isSafeInteger(Number(term)) ||
  Number(term) <= 0
    ) {
    alert("Введите корректную сумму и срок кредита.");
    return;
    }

  const updatedData: CreditApplication = {
    id: application?.id ?? crypto.randomUUID(),
    productName,
    amount: Number(amount),
    term: Number(term),
    purpose,
    companyName,
    inn,
    status: "draft",
    createdAt: application?.createdAt ?? new Date().toISOString(),
  };

  try {
    if (application && application.status !== "draft") {
      window.alert("Редактировать можно только черновик.");
      return;
    }
    if (application) {
      updateApplication(updatedData);
    } else {
      saveApplication(updatedData);
    }

    setSaved(true);
  } catch {
    alert("Не удалось сохранить черновик.");
  }
}



  if (saved) {
    return (
      <section className="application-form">
        <h2>Черновик заявки заполнен</h2>
        <p>
            Черновик заявки сохранён в этом браузере.
            Заявка не отправлена в банк.
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
            type="text"
            inputMode="numeric"
            pattern="[0-9]+"
            title="Введите сумму"
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
          <button type="submit">Сохранить черновик</button>
        </div>
      </form>
    </section>
  );
}
