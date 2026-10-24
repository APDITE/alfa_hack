
const API_URL = "/api/applications";
const TOKEN_KEY = "alfa-hack-access-token";

export type ProductId = "working_capital" | "equipment";

export type PurposeCategory =
  | "inventory"
  | "cash_gap"
  | "equipment"
  | "other";

export type CreateApplicationData = {
  product_id: ProductId;
  purpose_category?: PurposeCategory;
  amount?: number;
  term_months?: number;
  purpose?: string;
};

export type ApplicationSummary = {
  id: string;
  status: string;
  status_label: string;
  client_stage: string;
  stage_label: string;
  product_id: ProductId;
  amount: number | null;
  term_months: number | null;
  company_inn: string;
  company_name: string;
  risk_class: "low" | "medium" | "high" | null;
  created_at: string;
  updated_at: string;
};

export type ScoreFactor = {
  name: string;
  points: number;
  impact: "increases_risk" | "decreases_risk";
  comment: string;
};

export type ScoreView = {
  score: number;
  risk_class: "low" | "medium" | "high";
  points_total: number;
  factors: ScoreFactor[];
  model_version: string;
};

export type CheckResult = {
  type: "completeness" | "egrul" | "transparent_business" | "bki";
  outcome: "passed" | "failed" | "pending" | "unavailable";
  summary: string;
  attempt: number;
};

export type LoanTerms = {
  product_id: ProductId;
  amount: number;
  term_months: number;
  rate: number;
  monthly_payment: number;
};

export type DecisionView = {
  outcome: "approved" | "counter_offer" | "clarification" | "rejected";
  terms: LoanTerms | null;
  reason: string;
  rule: string;
  decided_by: string;
  comment: string | null;
  decided_at: string;
};

export type ClarificationView = {
  requested_fields: string[];
  message: string;
  answer: string | null;
};

export type ApplicationDetail = ApplicationSummary & {
  purpose_category: PurposeCategory | null;
  purpose: string | null;
  revenue_year: number | null;
  expenses_year: number | null;
  liabilities_total: number | null;
  submitted_at: string | null;
  available_actions: string[];
  next_step: string;
  waiting_external: boolean;

  company: {
    inn: string;
    name: string;
    legal_form: "OOO" | "IP";
    okved: string;
    registration_date: string;
    region: string;
    director: string;
  };

  history: {
    from_status: string | null;
    to_status: string;
    actor: string;
    comment: string | null;
    at: string;
  }[];

  checks: CheckResult[];
  score: ScoreView | null;
  decision: DecisionView | null;
  clarification: ClarificationView | null;
};

export type ManualDecisionOutcome =
  | "approved"
  | "rejected"
  | "clarification";

export type ManualDecisionData = {
  outcome: ManualDecisionOutcome;
  comment: string;
  requested_fields?: string[];
};

async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY);

  if (!token) {
    throw new Error("Необходимо войти в систему.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Ошибка сервера (${response.status})`;

    try {
      const data: unknown = await response.json();

      if (
        typeof data === "object" &&
        data !== null &&
        "detail" in data &&
        typeof data.detail === "string"
      ) {
        message = data.detail;
      }
    } catch {
      // Используем стандартное сообщение об ошибке.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function createApplication(
  data: CreateApplicationData
): Promise<ApplicationDetail> {
  return apiRequest("", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getApplications(): Promise<ApplicationSummary[]> {
  return apiRequest("");
}

export function getApplication(
  id: string
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}`);
}

export function updateApplication(
  id: string,
  data: Partial<CreateApplicationData>
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function submitApplication(
  id: string,
  idempotencyKey: string
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}/submit`, {
    method: "POST",
    headers: {
      "Idempotency-Key": idempotencyKey,
    },
  });
}

export function makeManualDecision(
  id: string,
  data: ManualDecisionData
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}/decision`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function respondToOffer(
  id: string,
  accept: boolean
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}/accept`, {
    method: "POST",
    body: JSON.stringify({ accept }),
  });
}

export function signApplication(
  id: string
): Promise<ApplicationDetail> {
  return apiRequest(`/${encodeURIComponent(id)}/sign`, {
    method: "POST",
  });
}
