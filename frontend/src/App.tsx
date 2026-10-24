import { useEffect, useState } from "react";

import "./App.css";
import { api, setUnauthorizedHandler, tokenStore } from "./api/client";
import type { AuthUser } from "./api/types";
import BankDashboard from "./components/BankDashboard";
import ClientCabinet from "./components/ClientCabinet";
import LoginForm from "./components/LoginForm";

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear();
      setUser(null);
      setSessionExpired(true);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!tokenStore.get()) {
      setCheckingSession(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setCheckingSession(false));
  }, []);

  function handleLogin(account: AuthUser, token: string) {
    tokenStore.set(token);
    setSessionExpired(false);
    setUser(account);
  }

  function handleLogout() {
    tokenStore.clear();
    setUser(null);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo" aria-hidden="true">
            ₽
          </span>
          <div>
            <h1>Умный кредитный кабинет</h1>
            <p>Прототип кредитного конвейера для малого бизнеса</p>
          </div>
        </div>
        {user && (
          <div className="topbar__user">
            <span>
              {user.full_name}
              <span className="muted"> · {user.role === "employee" ? "сотрудник банка" : "предприниматель"}</span>
            </span>
            <button type="button" className="button button--ghost" onClick={handleLogout}>
              Выйти
            </button>
          </div>
        )}
      </header>

      <main>
        {sessionExpired && !user && (
          <p className="notice" role="status">
            Сессия истекла — войдите снова.
          </p>
        )}
        {checkingSession ? (
          <p className="muted" role="status">
            Проверяем вход…
          </p>
        ) : !user ? (
          <LoginForm onLogin={handleLogin} />
        ) : user.role === "client" ? (
          <ClientCabinet key={user.id} user={user} />
        ) : (
          <BankDashboard key={user.id} />
        )}
      </main>
    </div>
  );
}
