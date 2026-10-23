
export type CreditApplication = {
  id: string;
  productName: string;
  amount: number;
  term: number;
  purpose: string;
  companyName: string;
  inn: string;
  status: "draft";
  createdAt: string;
};
