import { useEffect, useState } from "react";
import "./App.css";
import ProductCatalog from "./components/ProductCatalog";
import BankDashboard from "./components/BankDashboard";
import LoginForm, { type AuthUser } from "./components/LoginForm";

const TOKEN_KEY = "alfa-hack-access-token";

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) {
      setCheckingSession(false);
      return;
    }

    const controller = new AbortController();
    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Session invalid");
        return (await response.json()) as AuthUser;
      })
      .then((account) => {
        if (account.role !== "client" && account.role !== "employee") {
          throw new Error("Invalid role");
        }
        setUser(account);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        // If the server is temporarily unavailable, require a fresh sign-in.
        sessionStorage.removeItem(TOKEN_KEY);
        setUser(null);
        if (error instanceof Error) console.warn("Session check failed:", error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setCheckingSession(false);
      });

    return () => controller.abort();
  }, []);

  function handleLogin(account: AuthUser, token: string) {
    sessionStorage.setItem(TOKEN_KEY, token);
    setUser(account);
  }

  function handleLogout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }

  return (
    <div>
      <header>
        <h1>Умный кредитный кабинет</h1>
        <p>Альфа-Банк — учебный прототип</p>
      </header>

      {user && (
        <nav className="auth-navigation">
          <span>
            {user.full_name} · {user.role === "employee" ? "Сотрудник банка" : "Предприниматель"}
          </span>
          <button type="button" onClick={handleLogout}>Выйти</button>
        </nav>
      )}

      <main>
        {checkingSession ? (
          <p role="status">Проверяем авторизацию…</p>
        ) : !user ? (
          <LoginForm onLogin={handleLogin} />
        ) : user.role === "client" ? (
          <ProductCatalog />
        ) : (
          <BankDashboard />
        )}
      </main>
    </div>
  );
}

