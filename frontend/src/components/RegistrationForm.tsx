import { useState, type FormEvent } from "react";

import { api, errorText } from "../api/client";
import type { AuthUser, Company } from "../api/types";
import { date } from "../utils/format";

type Props = {
  onRegistered: (user: AuthUser, token: string) => void;
  onCancel: () => void;
};

/** Scenario 12: find the company by INN in the registry, then create the account. */
export default function RegistrationForm({ onRegistered, onCancel }: Props) {
  const [inn, setInn] = useState("");
  const [company, setCompany] = useState<Company | null>(null);
  const [fullName, setFullName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function find(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^\d{10}(\d{2})?$/.test(inn)) {
      setError("ИНН — 10 цифр для ООО или 12 для ИП.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const found = await api.registryCompany(inn);
      setCompany(found);
      setFullName((current) => current || found.director);
    } catch (caught) {
      setCompany(null);
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^[A-Za-z0-9_.-]{3,64}$/.test(login)) {
      setError("Логин: от 3 символов — латиница, цифры, точка, дефис или подчёркивание.");
      return;
    }
    if (password.length < 8) {
      setError("Пароль — не короче 8 символов.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = await api.register({ inn, full_name: fullName.trim(), login, password });
      onRegistered(data.user, data.access_token);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="login-form card">
      <h3>Регистрация компании</h3>
      {!company ? (
        <form className="stack" onSubmit={find} noValidate>
          <div className="field">
            <label htmlFor="reg-inn">ИНН компании или ИП</label>
            <input
              id="reg-inn"
              inputMode="numeric"
              autoComplete="off"
              maxLength={12}
              value={inn}
              onChange={(e) => setInn(e.target.value.replace(/\D/g, ""))}
              placeholder="10 или 12 цифр"
            />
          </div>
          <p className="muted small">
            Реквизиты подставим из ЕГРЮЛ/ЕГРИП. Реестр в демо синтетический: подойдёт любой ИНН
            из 10 или 12 цифр, а выручку банк спросит после отправки заявки.
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button button--primary button--large" disabled={busy}>
            {busy ? "Ищем…" : "Найти компанию"}
          </button>
          <button type="button" className="link-button" onClick={onCancel}>
            ← Ко входу
          </button>
        </form>
      ) : (
        <form className="stack" onSubmit={submit} noValidate>
          <div className="company-found">
            <strong>{company.name}</strong>
            <span>
              ИНН {company.inn} · ОКВЭД {company.okved}
            </span>
            <span>
              Руководитель {company.director}, на рынке с {date(company.registration_date)}
            </span>
          </div>
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setCompany(null);
              setError("");
            }}
          >
            Не ваша компания? Изменить ИНН
          </button>
          <div className="field">
            <label htmlFor="reg-name">Ваше имя</label>
            <input
              id="reg-name"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="reg-login">Логин</label>
            <input
              id="reg-login"
              autoComplete="username"
              value={login}
              onChange={(e) => setLogin(e.target.value.trim())}
            />
          </div>
          <div className="field">
            <label htmlFor="reg-password">Пароль, не короче 8 символов</label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button button--primary button--large" disabled={busy}>
            {busy ? "Регистрируем…" : "Зарегистрироваться и войти"}
          </button>
          <button type="button" className="link-button" onClick={onCancel}>
            ← Ко входу
          </button>
        </form>
      )}
    </section>
  );
}
