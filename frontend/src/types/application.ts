export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "review"
  | "clarification"
  | "approved"
  | "rejected"
  | "offer"
  | "accepted"
  | "declined";

export type CreditApplication = {
  id: string;
  productName: string;
  amount: number;
  term: number;
  purpose: string;
  companyName: string;
  inn: string;
  status: ApplicationStatus;
  createdAt: string;
  submittedAt?: string;
  clarificationRequest?: string;
  clarificationReply?: string;
  offerDetails?: string;
};
