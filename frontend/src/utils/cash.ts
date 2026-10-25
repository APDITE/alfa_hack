import type { CashPlan, CashSimulation } from "../api/types";
import { dayMonth, dayMonthYear, money } from "./format";

/** "28 ноября" this year, "20 февраля 2028 г." in another one. */
function when(iso: string): string {
  return iso.slice(0, 4) === String(new Date().getFullYear()) ? dayMonth(iso) : dayMonthYear(iso);
}

/** "разрыв с 28 ноября, до 207 800 ₽" or "разрыва нет": the first day short of money and the
 * deepest shortfall over the whole term. */
export function gapText(simulation: CashSimulation): string {
  return simulation.first_gap
    ? `разрыв с ${when(simulation.first_gap)}, до ${money(simulation.shortfall)}`
    : "разрыва нет";
}

/** "с 28 ноября; больше всего — 28 октября 2028 г.": when the gap starts and when it is deepest. */
export function gapDates(simulation: CashSimulation): string | null {
  if (!simulation.first_gap) return null;
  const first = `с ${when(simulation.first_gap)}`;
  return simulation.min_date === simulation.first_gap ? first : `${first}; больше всего — ${when(simulation.min_date)}`;
}

/** The saved choice in one line, for the client card and the bank workplace. */
export function cashPlanSummary(plan: CashPlan): string {
  return `как запланировано — ${gapText(plan.base)}; если поступления задержатся на неделю — ${gapText(plan.delayed)}`;
}
