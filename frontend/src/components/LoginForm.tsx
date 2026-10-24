import { useState, type FormEvent } from "react";

export type AuthUser = {
  id: string;
  login: string;
  full_name: string;
  role: "client" | "employee";
  company_inn: string | null;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

type Props = {
  onLogin: (user: AuthUser, token: string) => void;
};

export default function LoginForm({ onLogin }: Props) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });

      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Неверный логин или пароль"
            : `Ошибка сервера (${response.status})`
        );
      }

      const data: LoginResponse = await response.json();
      if (
        !data.access_token ||
        !data.user ||
        (data.user.role !== "client" && data.user.role !== "employee")
      ) {
        throw new Error("Сервер вернул некорректный ответ");
      }

      onLogin(data.user, data.access_token);
    } catch (err) {
      setError(
        err instanceof TypeError
          ? "Не удалось связаться с backend. Проверьте, что сервер запущен."
          : err instanceof Error
            ? err.message
            : "Ошибка входа"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-page">
      <div className="login-intro">
        <h2>Добро пожаловать!</h2>
        <p>Управляйте кредитными заявками в едином кабинете.</p>
      </div>
      <form className="login-form" onSubmit={handleSubmit}>
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
        {error && <p className="login-error" role="alert">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Выполняется вход…" : "Войти"}
        </button>
      </form>
    </section>
  );
}
