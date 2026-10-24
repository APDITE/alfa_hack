import type {
  Actor,
  ApplicationStatus,
  CheckResult,
  CheckType,
  ClientStage,
  DecisionOutcome,
  ProductId,
  PurposeCategory,
  RiskClass,
} from "../api/types";

export const PRODUCT_NAMES: Record<ProductId, string> = {
  working_capital: "Оборотный кредит",
  equipment: "Кредит на оборудование",
};

export const PURPOSE_LABELS: Record<PurposeCategory, string> = {
  inventory: "Закупка товара",
  cash_gap: "Кассовый разрыв",
  equipment: "Покупка оборудования",
  other: "Другие задачи бизнеса",
};

/** Fields the bank can ask the client to fill in (clarification requests). */
export const FIELD_LABELS: Record<string, string> = {
  revenue_year: "Выручка за последние 12 месяцев, ₽",
  expenses_year: "Расходы за последние 12 месяцев, ₽",
  liabilities_total: "Текущие долги и кредиты, ₽",
  amount: "Сумма кредита, ₽",
  term_months: "Срок кредита, мес.",
};

export const CHECK_LABELS: Record<CheckType, string> = {
  completeness: "Полнота заявки",
  egrul: "ЕГРЮЛ / ЕГРИП",
  transparent_business: "«Прозрачный бизнес» ФНС",
  bki: "Бюро кредитных историй",
};

export const CHECK_OUTCOME_LABELS: Record<CheckResult["outcome"], string> = {
  passed: "пройдена",
  failed: "есть замечания",
  pending: "выполняется",
  unavailable: "сервис недоступен",
};

export const FACTOR_LABELS: Record<string, string> = {
  credit_history: "Кредитная история",
  overdue_frequency: "Частота просрочек",
  debt_load: "Долговая нагрузка",
  profit_margin: "Рентабельность",
  company_age: "Возраст компании",
  revenue_size: "Размер выручки",
  loan_to_revenue: "Сумма к выручке",
  active_loans: "Действующие кредиты",
  term: "Срок кредита",
};

export const RISK_LABELS: Record<RiskClass, string> = {
  low: "Низкий риск",
  medium: "Средний риск",
  high: "Высокий риск",
};

export const ACTOR_LABELS: Record<Actor, string> = {
  client: "Клиент",
  system: "Система",
  employee: "Сотрудник",
};

export const OUTCOME_LABELS: Record<DecisionOutcome, string> = {
  approved: "Одобрено",
  counter_offer: "Другие условия",
  clarification: "Запрошены уточнения",
  rejected: "Отказ",
};

/** Plain-language names of the credit rules (backend `decision.rule`). */
export const RULE_LABELS: Record<string, string> = {
  approved: "все условия продукта выполнены",
  debt_load_longer_term: "нагрузка выше лимита — предложен больший срок",
  debt_load_smaller_amount: "нагрузка выше лимита — предложена меньшая сумма",
  debt_load_alternative: "нагрузка выше лимита — предложен другой продукт",
  debt_load_too_high: "нагрузка выше лимита при любых условиях",
  business_age_alternative: "возраст бизнеса — предложен другой продукт",
  business_too_young: "возраст бизнеса меньше минимального",
  pd_too_high: "оценка риска выше порога отказа",
  pd_grey_zone: "оценка риска в серой зоне",
  amount_above_auto_limit: "сумма выше лимита автоматического решения",
  terms_out_of_range: "сумма или срок вне лимитов продукта",
  missing_data: "не хватает данных",
  registry_liquidating: "компания в процессе ликвидации",
  registry_liquidated: "компания ликвидирована",
  registry_not_found: "компания не найдена в реестре",
  scoring_unavailable: "оценка риска недоступна",
  manual_decision: "решение сотрудника",
};

/** Statuses in which the bank's automatic pipeline is working on the application. */
export const IN_PROGRESS: ApplicationStatus[] = [
  "submitted",
  "data_check",
  "enrichment",
  "scoring",
  "credit_decision",
];

export const STAGE_TONE: Record<ClientStage, string> = {
  filling: "neutral",
  in_review: "info",
  action_required: "warning",
  decision_ready: "success",
  signing: "accent",
  completed: "neutral",
};

export function statusTone(status: ApplicationStatus, stage: ClientStage): string {
  if (status === "issued") return "success";
  if (status === "rejected") return "danger";
  return STAGE_TONE[stage];
}
