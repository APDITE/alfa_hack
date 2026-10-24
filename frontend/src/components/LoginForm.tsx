import { useState, type FormEvent } from "react";

import { api, errorText } from "../api/client";
import type { AuthUser } from "../api/types";
import RegistrationForm from "./RegistrationForm";

type Props = {
  onLogin: (user: AuthUser, token: string) => void;
};

// Synthetic test accounts from backend/config/demo_companies.yaml (password = login).
const DEMO_ACCOUNTS: { login: string; company: string; scenario: string }[] = [
  { login: "client1", company: "ООО «Северный ветер»", scenario: "автоодобрение" },
  { login: "client2", company: "ООО «Пекарня на углу»", scenario: "другие условия" },
  { login: "client3", company: "ИП Ковалёва", scenario: "банк запросит данные" },
  { login: "client4", company: "ООО «СтройМонтаж»", scenario: "отказ: просрочка" },
  { login: "client5", company: "ООО «Агротех»", scenario: "ручная проверка" },
  { login: "client6", company: "ООО «Вектор»", scenario: "отказ: ликвидация" },
  { login: "client7", company: "ООО «Кофейня Зерно»", scenario: "два продукта" },
  { login: "client8", company: "ИП Захаров", scenario: "молодой бизнес" },
  { login: "analyst", company: "Сотрудник банка", scenario: "ручная проверка заявок" },
];

export default function LoginForm({ onLogin }: Props) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [registering, setRegistering] = useState(false);

  async function signIn(loginValue: string, passwordValue: string) {
    setError("");
    setLoading(true);
    try {
      const data = await api.login(loginValue, passwordValue);
      onLogin(data.user, data.access_token);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void signIn(login.trim(), password);
  }

  return (
    <section className="login-page">
      <div className="login-intro">
        <h2>Кредит для бизнеса — в одном кабинете</h2>
        <p>
          Подберите продукт под задачу, подайте заявку и следите за решением. Банк проверит
          данные компании сам: реквизиты, выручку и кредитную историю.
        </p>
        <div className="demo-accounts">
          <h3>Демо-доступ</h3>
          <p className="muted">Нажмите на учётную запись, чтобы войти. Пароль совпадает с логином.</p>
          <ul>
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.login}>
                <button
                  type="button"
                  className="demo-account"
                  disabled={loading}
                  onClick={() => {
                    setRegistering(false);
                    setLogin(account.login);
                    setPassword(account.login);
                    void signIn(account.login, account.login);
                  }}
                >
                  <span className="demo-account__login">{account.login}</span>
                  <span className="demo-account__company">{account.company}</span>
                  <span className="demo-account__scenario">{account.scenario}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {registering ? (
        <RegistrationForm onRegistered={onLogin} onCancel={() => setRegistering(false)} />
      ) : (
        <form className="login-form card" onSubmit={handleSubmit}>
          <h3>Вход в систему</h3>
          <label htmlFor="auth-login">Логин</label>
          <input
            id="auth-login"
            type="text"
            autoComplete="username"
            required
            value={login}
            onChange={(event) => setLogin(event.target.value)}
          />
          <label htmlFor="auth-password">Пароль</label>
          <input
            id="auth-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button button--primary" disabled={loading}>
            {loading ? "Входим…" : "Войти"}
          </button>
          <button type="button" className="link-button" onClick={() => setRegistering(true)}>
            Нет учётной записи? Зарегистрируйте компанию по ИНН
          </button>
        </form>
      )}
    </section>
  );
}
