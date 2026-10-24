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

  const signedInClient = !checkingSession && user?.role === "client";

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner container">
          <div className="topbar__brand">
            <h1 className="topbar__title">Умный кредитный кабинет</h1>
            <span className="topbar__subtitle">Кредиты для малого бизнеса</span>
          </div>
          {user && (
            <div className="topbar__user">
              <div className="topbar__who">
                <span className="topbar__name">{user.full_name}</span>
                <span className="topbar__role">
                  {user.role === "employee" ? "Сотрудник банка" : "Предприниматель"}
                </span>
              </div>
              <button type="button" className="button button--secondary button--small" onClick={handleLogout}>
                Выйти
              </button>
            </div>
          )}
        </div>
      </header>

      <main>
        {signedInClient && user ? (
          <ClientCabinet key={user.id} user={user} />
        ) : (
          <div className="container page">
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
            ) : (
              <BankDashboard key={user.id} />
            )}
          </div>
        )}
      </main>
    </div>
  );
}
