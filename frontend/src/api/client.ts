// HTTP client for the backend: auth token, error messages in Russian, all endpoints.

import { money } from "../utils/format";
import type {
  ApplicationDetail,
  ApplicationSummary,
  AuthUser,
  Availability,
  CashCalendarData,
  CashPreview,
  ClarificationAnswer,
  Company,
  DraftInput,
  ExternalService,
  Feed,
  LifecycleMeta,
  LoginResponse,
  ManualDecision,
  OpsSummary,
  Preapproval,
  Product,
  PurposeCategory,
  Recommendation,
  RegistrationInput,
} from "./types";

const TOKEN_KEY = "alfa-hack-access-token";

export const tokenStore = {
  get: (): string | null => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string): void => sessionStorage.setItem(TOKEN_KEY, token),
  clear: (): void => sessionStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let onUnauthorized: (() => void) | null = null;

/** Called when the backend answers 401 to a signed-in request (expired token). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

// Backend messages are for developers; the client sees these instead.
const KNOWN_ERRORS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^amount must be between (\d+) and (\d+)$/, (m) =>
    `Сумма должна быть от ${money(Number(m[1]))} до ${money(Number(m[2]))}.`],
  [/^term_months must be between (\d+) and (\d+)$/, (m) =>
    `Срок должен быть от ${m[1]} до ${m[2]} мес.`],
  [/^amount is required$/, () => "Укажите сумму кредита."],
  [/^term_months is required$/, () => "Укажите срок кредита."],
  [/^Only a draft can be submitted/, () => "Отправить можно только черновик."],
  [/cannot be edited$/, () => "Эту заявку сейчас нельзя изменить."],
  [/^Idempotency-Key was already used/, () => "Эта заявка уже отправлена."],
  [/^There is no offer to respond to$/, () => "По заявке сейчас нет предложения банка."],
  [/^Only applications in manual review/, () =>
    "Решение можно принять только по заявке на ручной проверке."],
  [/^amount out of product range$/, () => "Сумма вне лимитов продукта."],
  [/^term out of product range$/, () => "Срок вне лимитов продукта."],
  [/^terms are required for counter_offer$/, () => "Укажите условия предложения."],
  [/^Transition .* is not allowed$/, () => "Это действие недоступно в текущем статусе заявки."],
  [/cannot move an application/, () => "Сейчас заявку обрабатывает банк, действие недоступно."],
  [/^Application not found$/, () => "Заявка не найдена."],
  [/^This application belongs to another company$/, () => "Это заявка другой компании."],
  [/^Only clients can do this$/, () => "Действие доступно только клиенту."],
  [/^Only bank employees can do this$/, () => "Действие доступно только сотруднику банка."],
  [/^Invalid login or password$/, () => "Неверный логин или пароль."],
  [/^The payment day is chosen for an offer, before signing$/, () =>
    "Дату платежа выбирают для предложения банка, до подписания."],
  [/^There is no offer to plan payments for$/, () => "Пока нет предложения банка — планировать платежи рано."],
  [/^Company is already registered$/, () =>
    "Эта компания уже зарегистрирована — войдите под её учётной записью."],
  [/^Login is already taken$/, () => "Этот логин уже занят, выберите другой."],
  [/^Company not found in the registry$/, () => "Компания с таким ИНН не найдена в ЕГРЮЛ/ЕГРИП."],
  [/^Registry is temporarily unavailable$/, () => "Реестр временно недоступен, попробуйте через минуту."],
  [/^INN must be 10 or 12 digits$/, () => "ИНН — 10 цифр для ООО или 12 для ИП."],
  [/^Not authenticated$/, () => "Сессия истекла, войдите снова."],
];

const FIELD_NAMES: Record<string, string> = {
  amount: "сумма",
  term_months: "срок",
  purpose: "цель",
  revenue_year: "выручка",
  expenses_year: "расходы",
  liabilities_total: "долги",
  comment: "комментарий",
  rate: "ставка",
  inn: "ИНН",
  login: "логин",
  password: "пароль",
  full_name: "имя",
};

function translate(message: string): string {
  for (const [pattern, render] of KNOWN_ERRORS) {
    const found = message.match(pattern);
    if (found) return render(found);
  }
  return message;
}

function describe(item: unknown): string | null {
  if (typeof item === "string") return translate(item);
  if (typeof item === "object" && item !== null && "loc" in item && Array.isArray(item.loc)) {
    const field = String(item.loc[item.loc.length - 1]);
    return `Проверьте поле «${FIELD_NAMES[field] ?? field}».`;
  }
  return null;
}

async function errorMessage(response: Response): Promise<string> {
  let detail: unknown = null;
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) detail = body.detail;
  } catch {
    // No JSON body: fall back to the status code.
  }
  if (typeof detail === "string") return translate(detail);
  if (Array.isArray(detail)) {
    const parts = detail.map(describe).filter((p): p is string => p !== null);
    if (parts.length > 0) return parts.join(" ");
  }
  if (response.status >= 500) return "Сервер временно недоступен. Попробуйте ещё раз.";
  return `Не удалось выполнить запрос (${response.status}).`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError("Нет связи с сервером. Проверьте, что приложение запущено.", 0);
  }
  if (response.status === 401 && token && path !== "/api/auth/login") onUnauthorized?.();
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown): string => JSON.stringify(body);
const app = (id: string, action = ""): string =>
  `/api/applications/${encodeURIComponent(id)}${action ? `/${action}` : ""}`;

export const api = {
  login: (login: string, password: string) =>
    request<LoginResponse>("/api/auth/login", { method: "POST", body: json({ login, password }) }),
  me: () => request<AuthUser>("/api/auth/me"),
  registryCompany: (inn: string) =>
    request<Company>(`/api/registration/company/${encodeURIComponent(inn)}`),
  register: (input: RegistrationInput) =>
    request<LoginResponse>("/api/registration", { method: "POST", body: json(input) }),

  products: () => request<Product[]>("/api/products"),
  recommend: (purpose_category: PurposeCategory) =>
    request<Recommendation>("/api/products/recommend", {
      method: "POST",
      body: json({ purpose_category }),
    }),
  company: (inn: string) => request<Company>(`/api/companies/lookup/${encodeURIComponent(inn)}`),
  preapproved: () => request<Preapproval>("/api/offers/preapproved"),
  lifecycle: () => request<LifecycleMeta>("/api/meta/lifecycle"),

  applications: () => request<ApplicationSummary[]>("/api/applications"),
  application: (id: string) => request<ApplicationDetail>(app(id)),
  createDraft: (input: DraftInput) =>
    request<ApplicationDetail>("/api/applications", { method: "POST", body: json(input) }),
  updateDraft: (id: string, input: Partial<DraftInput>) =>
    request<ApplicationDetail>(app(id), { method: "PUT", body: json(input) }),
  answerClarification: (id: string, answer: ClarificationAnswer) =>
    request<ApplicationDetail>(app(id), { method: "PUT", body: json(answer) }),
  submit: (id: string, idempotencyKey: string) =>
    request<ApplicationDetail>(app(id, "submit"), {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  respondToOffer: (id: string, accept: boolean) =>
    request<ApplicationDetail>(app(id, "accept"), { method: "POST", body: json({ accept }) }),
  sign: (id: string) => request<ApplicationDetail>(app(id, "sign"), { method: "POST" }),
  cashPreview: (id: string, body: { calendar?: CashCalendarData; payment_day?: number }) =>
    request<CashPreview>(app(id, "cash-calendar/preview"), { method: "POST", body: json(body) }),
  saveCashPlan: (id: string, calendar: CashCalendarData, payment_day: number) =>
    request<ApplicationDetail>(app(id, "cash-calendar"), {
      method: "PUT",
      body: json({ calendar, payment_day }),
    }),
  withdraw: (id: string, reason?: string) =>
    request<ApplicationDetail>(app(id, "withdraw"), {
      method: "POST",
      body: json({ reason: reason ?? null }),
    }),
  decide: (id: string, decision: ManualDecision) =>
    request<ApplicationDetail>(app(id, "decision"), { method: "POST", body: json(decision) }),

  feed: () => request<Feed>("/api/feed"),
  markFeedRead: () => request<void>("/api/feed/read", { method: "POST" }),

  opsSummary: () => request<OpsSummary>("/api/ops/summary"),

  // Demo only: availability switches of the external-service mocks (scenario 7).
  availability: () => request<Availability>("/mock/admin/availability"),
  setAvailability: (service: ExternalService, available: boolean) =>
    request<Availability>("/mock/admin/availability", {
      method: "POST",
      body: json({ service, available }),
    }),
};

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла неизвестная ошибка.";
}
