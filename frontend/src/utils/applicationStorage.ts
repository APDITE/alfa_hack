
import type { CreditApplication } from "../types/application";

const STORAGE_KEY = "credit-applications-demo";

export function getApplications(): CreditApplication[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) as CreditApplication[] : [];
  } catch {
    return [];
  }
}

export function saveApplication(application: CreditApplication): void {
  const applications = getApplications();
  applications.push(application);

  localStorage.setItem(STORAGE_KEY, JSON.stringify(applications));
}

export function updateApplication(
  updatedApplication: CreditApplication
): void {
  const applications = getApplications();

  const updated = applications.map((application) =>
    application.id === updatedApplication.id
      ? updatedApplication
      : application
  );

  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
}

export function deleteApplication(id: string): void {
  const applications = getApplications();

  const filtered = applications.filter(
    (application) => application.id !== id
  );

  localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
}
