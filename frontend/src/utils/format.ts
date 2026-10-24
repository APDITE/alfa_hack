const numberFormat = new Intl.NumberFormat("ru-RU");

/** 1500000 -> "1 500 000 ₽" (non-breaking spaces). */
export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${numberFormat.format(value)} ₽`;
}

export function months(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value} мес.`;
}

/** Russian plural: plural(1, ["платёж", "платежа", "платежей"]) -> "платёж". */
export function plural(count: number, forms: [string, string, string]): string {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return forms[2];
  if (units === 1) return forms[0];
  if (units >= 2 && units <= 4) return forms[1];
  return forms[2];
}

export function percent(value: number): string {
  return `${value.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}%`;
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU");
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return "только что";
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  return date(iso);
}

/** Monthly annuity payment in rubles, the same formula as the backend credit rules. */
export function annuityPayment(amount: number, annualRatePercent: number, term: number): number {
  const monthlyRate = annualRatePercent / 100 / 12;
  if (monthlyRate === 0) return Math.round(amount / term);
  return Math.round((amount * monthlyRate) / (1 - (1 + monthlyRate) ** -term));
}

/** "1 500 000" or "1500000" -> 1500000; null for empty or non-numeric input. */
export function parseInteger(text: string): number | null {
  const digits = text.replace(/[\s  ]/g, "");
  if (!/^\d+$/.test(digits)) return null;
  const value = Number(digits);
  return Number.isSafeInteger(value) ? value : null;
}

/** Group digits while typing: "1500000" -> "1 500 000". */
export function groupDigits(text: string): string {
  const digits = text.replace(/\D/g, "");
  return digits ? numberFormat.format(Number(digits)) : "";
}

/** A random key for Idempotency-Key; works on plain HTTP too, unlike crypto.randomUUID. */
export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function" && window.isSecureContext) {
    return crypto.randomUUID();
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
