
import type { CreditApplication } from "../types/application";

const STORAGE_KEY = "credit-applications-demo";

export function getApplications(): CreditApplication[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return [];

    const parsed: unknown = JSON.parse(data);

    return Array.isArray(parsed)
      ? parsed.filter((item): item is CreditApplication =>
          typeof item === "object" &&
          item !== null &&
          typeof item.id === "string" &&
          typeof item.status === "string"
        )
      : [];
  } catch {
    return [];
  }
}

function writeApplications(
  applications: CreditApplication[]
): void {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(applications)
  );
}

export function saveApplication(
  application: CreditApplication
): void {
  writeApplications([...getApplications(), application]);
}

export function updateApplication(
  updatedApplication: CreditApplication
): void {
  const applications = getApplications();

  if (
    !applications.some(
      (item) => item.id === updatedApplication.id
    )
  ) {
    throw new Error("Заявка не найдена");
  }

  writeApplications(
    applications.map((item) =>
      item.id === updatedApplication.id
        ? updatedApplication
        : item
    )
  );
}

export function deleteApplication(id: string): void {
  writeApplications(
    getApplications().filter((item) => item.id !== id)
  );
}
