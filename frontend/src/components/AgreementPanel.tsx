import { useState } from "react";

import { api, errorText } from "../api/client";
import type { AgreementDocument, AgreementSummary } from "../api/types";
import { dateTime } from "../utils/format";

/** SHA-256 of the text in the browser; null where Web Crypto is unavailable (plain HTTP). */
async function sha256Hex(text: string): Promise<string | null> {
  if (!window.isSecureContext || !globalThis.crypto?.subtle) return null;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

type Props = {
  applicationId: string;
  /** All versions, oldest first; the latest one is shown. */
  agreements: AgreementSummary[];
};

/** The loan agreement: number, version and SHA-256, the text, a download and a check of the hash. */
export default function AgreementPanel({ applicationId, agreements }: Props) {
  const latest = agreements[agreements.length - 1];
  const [doc, setDoc] = useState<AgreementDocument | null>(null);
  const [open, setOpen] = useState(false);
  const [check, setCheck] = useState<{ ok: boolean; text: string } | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  if (!latest) return null;

  async function load(): Promise<AgreementDocument> {
    if (doc && doc.version === latest.version) return doc;
    const loaded = await api.agreement(applicationId, latest.version);
    setDoc(loaded);
    return loaded;
  }

  async function toggleText() {
    setError("");
    if (!open) {
      try {
        await load();
      } catch (caught) {
        setError(errorText(caught));
        return;
      }
    }
    setOpen((value) => !value);
  }

  async function download() {
    setError("");
    try {
      const loaded = await load();
      const url = URL.createObjectURL(new Blob([loaded.text], { type: "text/plain;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `${loaded.number}-редакция-${loaded.version}.txt`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  async function verify() {
    setError("");
    try {
      const loaded = await load();
      const local = await sha256Hex(loaded.text);
      if (local === null) {
        setCheck({
          ok: loaded.verified,
          text: loaded.verified
            ? "Хеш текста совпадает с хешем договора (проверено на сервере): документ не менялся."
            : "Хеш текста не совпадает с хешем договора: документ изменён.",
        });
        return;
      }
      const ok = local === latest.sha256;
      setCheck({
        ok,
        text: ok
          ? "SHA-256 текста, посчитанный в вашем браузере, совпадает с хешем договора: документ не менялся."
          : "SHA-256 текста не совпадает с хешем договора: документ изменён.",
      });
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(latest.sha256);
      setCopied(true);
    } catch {
      // Clipboard is unavailable on plain HTTP: the hash stays selectable on the page.
    }
  }

  return (
    <section className="agreement" aria-label="Кредитный договор">
      <div className="agreement__head">
        <div className="agreement__title">
          <strong>Кредитный договор № {latest.number}</strong>
          <span className="muted small">
            Редакция {latest.version} от {dateTime(latest.created_at)} · {latest.reason}
          </span>
        </div>
        <span className={`badge badge--${latest.signed_at ? "success" : "info"}`}>
          {latest.signed_at ? `Подписан ${dateTime(latest.signed_at)}` : "Ждёт подписи"}
        </span>
      </div>
      <div className="agreement__hash">
        <span className="agreement__hash-label">SHA-256</span>
        <code>{latest.sha256}</code>
        <button type="button" className="link-button" onClick={() => void copy()}>
          {copied ? "Скопирован" : "Копировать"}
        </button>
      </div>
      <p className="muted small">
        Хеш — отпечаток текста договора: изменится хоть один символ — изменится и хеш. Подписывается именно
        эта редакция.
      </p>
      <div className="actions">
        <button type="button" className="button button--secondary button--small" onClick={() => void toggleText()}>
          {open ? "Скрыть текст" : "Открыть текст"}
        </button>
        <button type="button" className="button button--secondary button--small" onClick={() => void download()}>
          Скачать .txt
        </button>
        <button type="button" className="button button--secondary button--small" onClick={() => void verify()}>
          Проверить подлинность
        </button>
      </div>
      {check && (
        <p className={`agreement__check ${check.ok ? "is-ok" : "is-bad"}`} role="status">
          {check.text}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {open && doc && <pre className="agreement__text">{doc.text}</pre>}
      {agreements.length > 1 && (
        <details className="agreement__versions">
          <summary>Все редакции ({agreements.length})</summary>
          <ul>
            {agreements.map((item) => (
              <li key={item.version}>
                Редакция {item.version} · {dateTime(item.created_at)} · {item.reason} ·{" "}
                <code>{item.sha256.slice(0, 16)}…</code>
                {item.signed_at ? " · подписана" : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
