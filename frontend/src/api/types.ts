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

export type HistoryItem = {
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  actor: Actor;
  comment: string | null;
  at: string;
};

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
  clarification: Clarification | null;
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
