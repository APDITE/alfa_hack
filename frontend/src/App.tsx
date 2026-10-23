import { useState } from "react";
import "./App.css";
import ProductCatalog from "./components/ProductCatalog";
import BankDashboard from "./components/BankDashboard";

type Page = "home" | "client" | "bank";

export default function App() {
  const [page, setPage] = useState<Page>("home");

  return (
    <div>
      <header>
        <h1>Умный кредитный кабинет</h1>
        <p>Альфа-Банк — учебный прототип</p>
      </header>

      <nav>
        <button onClick={() => setPage("home")}>
          Главная
        </button>

        <button onClick={() => setPage("client")}>
          Кабинет предпринимателя
        </button>

        <button onClick={() => setPage("bank")}>
          Кабинет сотрудника банка
        </button>
      </nav>

      <main>
        {page === "home" && (
          <section>
            <h2>Главная страница</h2>
            <p>
              Добро пожаловать в умный кредитный кабинет.
              Здесь предприниматели могут подавать заявки
              на кредит и отслеживать их рассмотрение.
            </p>
          </section>
        )}

        {page === "client" && <ProductCatalog />}

        {page === "bank" && <BankDashboard />}
      </main>
    </div>
  );
}
