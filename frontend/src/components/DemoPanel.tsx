import { useEffect, useState } from "react";

import { api, errorText } from "../api/client";
import type { Availability, ExternalService } from "../api/types";

const SERVICES: { id: ExternalService; label: string }[] = [
  { id: "egrul", label: "ЕГРЮЛ / ЕГРИП" },
  { id: "transparent_business", label: "«Прозрачный бизнес»" },
  { id: "bki", label: "Бюро кредитных историй" },
];

/** Demo only: switch the external-service mocks off and on to show retries (scenario 7). */
export default function DemoPanel() {
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    api
      .availability()
      .then((data) => {
        setAvailability(data);
        setError("");
      })
      .catch((caught: unknown) => setError(errorText(caught)));
  }, [open]);

  async function toggle(service: ExternalService, available: boolean) {
    const previous = availability;
    // Optimistic: the switch moves at once and rolls back if the mock does not answer.
    setAvailability((current) => (current ? { ...current, [service]: available } : current));
    try {
      setAvailability(await api.setAvailability(service, available));
      setError("");
    } catch (caught) {
      setAvailability(previous);
      setError(errorText(caught));
    }
  }

  return (
    <div className="demo-panel">
      <button type="button" className="link-button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? "Скрыть демо-панель" : "Демо: сбои внешних сервисов"}
      </button>
      {open && (
        <div className="demo-panel__body">
          <p className="muted small">
            Выключите сервис и подайте заявку: конвейер будет повторять запрос, клиент увидит
            «Ждём ответ от внешней службы». После включения заявка продолжится сама; после
            10 неудачных попыток её получит сотрудник.
          </p>
          {error && <p className="form-error">{error}</p>}
          {availability && (
            <ul className="switches">
              {SERVICES.map((service) => (
                <li key={service.id}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={availability[service.id]}
                      onChange={(e) => void toggle(service.id, e.target.checked)}
                    />
                    <span>{service.label}</span>
                    <span className={availability[service.id] ? "ok" : "down"}>
                      {availability[service.id] ? "работает" : "недоступен"}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
