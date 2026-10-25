// Types of the backend API (see docs/openapi.json). Field names match the backend schemas.

export type ProductId = "working_capital" | "equipment";

export type PurposeCategory = "inventory" | "cash_gap" | "equipment" | "other";

export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "data_check"
  | "clarification_required"
  | "enrichment"
  | "scoring"
  | "credit_decision"
  | "manual_review"
  | "approved"
  | "counter_offer"
  | "rejected"
  | "signing"
  | "issued"
  | "withdrawn";

export type ClientStage =
  | "filling"
  | "in_review"
  | "action_required"
  | "decision_ready"
  | "signing"
  | "completed";

export type Actor = "client" | "system" | "employee";

export type RiskClass = "low" | "medium" | "high";

export type ApplicationAction =
  | "edit"
  | "submit"
  | "answer_clarification"
  | "accept"
  | "propose"
  | "decline"
  | "sign"
  | "withdraw"
  | "decide";

export type DecisionOutcome = "approved" | "counter_offer" | "clarification" | "rejected";

export type AuthUser = {
  id: string;
  login: string;
  full_name: string;
  role: "client" | "employee";
  company_inn: string | null;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export type Product = {
  id: ProductId;
  name: string;
  description: string;
  purposes: PurposeCategory[];
  min_amount: number;
  max_amount: number;
  min_term_months: number;
  max_term_months: number;
  base_rate: number;
  min_business_age_months: number;
};

export type Recommendation = {
  product: Product;
  reason: string;
};

export type Company = {
  inn: string;
  name: string;
  legal_form: "OOO" | "IP";
  okved: string;
  registration_date: string;
  region: string;
  director: string;
};

export type ApplicationSummary = {
  id: string;
  status: ApplicationStatus;
  status_label: string;
  client_stage: ClientStage;
  stage_label: string;
  product_id: ProductId;
  amount: number | null;
  term_months: number | null;
  company_inn: string;
  company_name: string;
  risk_class: RiskClass | null;
  created_at: string;
  updated_at: string;
};

export type LoanTerms = {
  product_id: ProductId;
  amount: number;
  term_months: number;
  rate: number;
  monthly_payment: number;
};

export type Decision = {
  outcome: DecisionOutcome;
  terms: LoanTerms | null;
  reason: string;
  rule: string;
  decided_by: Actor;
  comment: string | null;
  decided_at: string;
};

export type Clarification = {
  requested_fields: string[];
  message: string;
  answer: string | null;
};

export type CheckType = "completeness" | "egrul" | "transparent_business" | "bki";

export type CheckResult = {
  type: CheckType;
  outcome: "passed" | "failed" | "pending" | "unavailable";
  summary: string;
  attempt: number;
};

export type ScoreFactor = {
  name: string;
  points: number;
  impact: "increases_risk" | "decreases_risk";
  comment: string;
};

export type Score = {
  score: number;
  risk_class: RiskClass;
  points_total: number;
  factors: ScoreFactor[];
  model_version: string;
};

export type HistoryKind = "status" | "proposal" | "offer" | "agreement";

/** A status change; a new version of the agreement is listed too (from = to = signing). */
export type HistoryItem = {
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  actor: Actor;
  comment: string | null;
  at: string;
  kind: HistoryKind;
  /** Terms of an offer or proposal, the agreement and its hash. */
  details: string | null;
};

export type ProposalInput = {
  amount: number;
  term_months: number;
  rate: number | null;
  comment: string;
};

export type Proposal = {
  round: number;
  /** The bank's version the client answered. */
  offer_version: number;
  amount: number;
  term_months: number;
  rate: number | null;
  monthly_payment: number;
  comment: string;
  created_at: string;
  answered: boolean;
  answer_version: number | null;
};

export type OfferVersion = {
  version: number;
  terms: LoanTerms;
  total_interest: number;
  decided_by: Actor;
  reason: string;
  created_at: string;
  /** Round of the client's proposal this version answers. */
  in_reply_to: number | null;
};

export type Negotiation = {
  versions: OfferVersion[];
  proposals: Proposal[];
  max_rounds: number;
  rounds_left: number;
};

export type AgreementSummary = {
  number: string;
  version: number;
  offer_version: number;
  reason: string;
  sha256: string;
  created_at: string;
  signed_at: string | null;
};

export type AgreementDocument = AgreementSummary & { text: string; verified: boolean };

export type ApplicationDetail = ApplicationSummary & {
  purpose_category: PurposeCategory | null;
  purpose: string | null;
  revenue_year: number | null;
  expenses_year: number | null;
  liabilities_total: number | null;
  submitted_at: string | null;
  available_actions: ApplicationAction[];
  next_step: string;
  waiting_external: boolean;
  company: Company;
  history: HistoryItem[];
  checks: CheckResult[];
  score: Score | null;
  decision: Decision | null;
  /** Payment schedule for the offered or signed terms. */
  schedule: PaymentSchedule | null;
  /** Payment day chosen with the cash calendar. */
  cash_plan: CashPlan | null;
  /** The bank's offer versions and the client's proposals. */
  negotiation: Negotiation | null;
  /** Versions of the loan agreement, oldest first. */
  agreements: AgreementSummary[];
  clarification: Clarification | null;
};

export type SchedulePayment = {
  number: number;
  payment: number;
  principal: number;
  interest: number;
  /** Debt left after this payment. */
  balance: number;
  /** Once a payment day is chosen. */
  due_date: string | null;
};

export type PaymentSchedule = {
  payments: SchedulePayment[];
  total_paid: number;
  /** Interest over the whole term. */
  overpayment: number;
  payment_day: number | null;
  /** Actual issue date, or today until the loan is issued. */
  issue_date: string | null;
};

/** One line of the client's typical month: positive — a receipt, negative — a payment. */
export type CashEvent = { day: number; amount: number; label: string };

export type CashCalendarData = {
  /** Balance at the start of the month of the first loan payment. */
  opening_balance: number;
  /** Balance to keep; below it is a cash gap. */
  reserve: number;
  events: CashEvent[];
};

export type CashSimulation = {
  min_balance: number;
  min_date: string;
  first_gap: string | null;
  /** Missing below the reserve at the worst moment. */
  shortfall: number;
};

export type PaymentDayOption = {
  payment_day: number;
  first_payment_date: string;
  first_payment: number;
  /** Interest above the cheapest compared day. */
  extra_cost: number;
  base: CashSimulation;
  /** Every receipt a week late. */
  delayed: CashSimulation;
};

/** The lowest balance of a day; for loans longer than two years, of a few days. */
export type BalancePoint = { day: string; balance: number };

export type CashPreview = {
  calendar: CashCalendarData;
  template: boolean;
  payment_day: number;
  recommended_day: number | null;
  recommendation: string;
  options: PaymentDayOption[];
  chart_base: BalancePoint[];
  chart_delayed: BalancePoint[];
};

export type CashPlan = {
  payment_day: number;
  calendar: CashCalendarData;
  base: CashSimulation;
  delayed: CashSimulation;
};

/** What the bank would approve automatically right now, per product. */
export type Preapproval = {
  offers: LoanTerms[];
  reason: string | null;
};

export type DraftInput = {
  product_id: ProductId;
  purpose_category?: PurposeCategory | null;
  amount?: number;
  term_months?: number;
  purpose?: string;
};

export type FinancialField = "revenue_year" | "expenses_year" | "liabilities_total";

export type ClarificationAnswer = Partial<Record<FinancialField | "amount" | "term_months", number>> & {
  clarification_answer?: string;
};

export type ManualDecision = {
  outcome: DecisionOutcome;
  comment: string;
  terms?: {
    product_id: ProductId;
    amount: number;
    term_months: number;
    rate?: number | null;
  };
  requested_fields?: string[];
};

export type FeedItem = {
  id: string;
  type: "event";
  title: string;
  text: string;
  application_id: string | null;
  created_at: string;
  read: boolean;
};

export type Feed = {
  events: FeedItem[];
  unread_events: number;
};

export type LifecycleMeta = {
  statuses: {
    status: ApplicationStatus;
    label: string;
    client_stage: ClientStage;
    turn_owner: Actor | null;
    allowed_next: ApplicationStatus[];
  }[];
  stages: { stage: ClientStage; label: string }[];
};

export type ExternalService = "egrul" | "transparent_business" | "bki";

export type Availability = Record<ExternalService, boolean>;

export type OpsSummary = {
  status: "ok" | "warning" | "critical";
  ready_jobs: number;
  oldest_ready_seconds: number;
  stuck_applications: number;
  waiting_external: number;
  failed_jobs_24h: number;
  manual_review: number;
  alerts: { level: "warning" | "critical"; text: string }[];
};

export type RegistrationInput = {
  inn: string;
  full_name: string;
  login: string;
  password: string;
};
