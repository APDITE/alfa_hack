import type { PaymentSchedule } from "../api/types";
import { date, money, plural } from "../utils/format";

type Props = {
  schedule: PaymentSchedule;
  /** Open where the client confirms they have read it (signing). */
  open?: boolean;
  /** The loan is issued: dates count from the actual issue, not from today. */
  issued?: boolean;
};

/** Monthly payments for the offered or signed terms, as calculated by the bank. */
export default function PaymentScheduleView({ schedule, open = false, issued = false }: Props) {
  const { payments, total_paid: totalPaid, overpayment } = schedule;
  if (payments.length === 0) return null;
  const first = payments[0];
  const regular = payments.length > 1 ? payments[1].payment : first.payment;
  const last = payments[payments.length - 1];
  const dated = first.due_date !== null && schedule.issue_date !== null;
  const firstDays =
    dated && first.due_date && schedule.issue_date
      ? Math.round(
          (new Date(`${first.due_date}T12:00:00`).getTime() -
            new Date(`${schedule.issue_date}T12:00:00`).getTime()) /
            86_400_000,
        )
      : null;

  return (
    <details className="schedule" open={open}>
      <summary className="schedule__summary">
        <span className="schedule__title">График платежей</span>
        <span className="schedule__meta">
          {payments.length} {plural(payments.length, ["платёж", "платежа", "платежей"])} по{" "}
          {money(regular)} · переплата {money(overpayment)}
        </span>
      </summary>
      <div className="schedule__scroll" role="region" aria-label="График платежей по месяцам" tabIndex={0}>
        <table className="schedule__table">
          <thead>
            <tr>
              <th scope="col">№</th>
              {dated && <th scope="col">Дата</th>}
              <th scope="col">Платёж</th>
              <th scope="col">Основной долг</th>
              <th scope="col">Проценты</th>
              <th scope="col">Остаток долга</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((payment) => (
              <tr key={payment.number}>
                <td>{payment.number}</td>
                {dated && <td>{payment.due_date ? date(payment.due_date) : "—"}</td>}
                <td>{money(payment.payment)}</td>
                <td>{money(payment.principal)}</td>
                <td>{money(payment.interest)}</td>
                <td>{money(payment.balance)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Итого</th>
              {dated && <td />}
              <td>{money(totalPaid)}</td>
              <td>{money(totalPaid - overpayment)}</td>
              <td>{money(overpayment)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="schedule__note muted small">
        {dated && schedule.issue_date && firstDays !== null
          ? `Платёж ${schedule.payment_day}-го числа каждого месяца. ${
              issued
                ? `Даты — от выдачи ${date(schedule.issue_date)}`
                : `Даты — если кредит выдадут сегодня, ${date(schedule.issue_date)}`
            }; первый платёж включает проценты за ${firstDays} ${plural(firstDays, ["день", "дня", "дней"])}.`
          : "Платёж раз в месяц, первый — через месяц после выдачи."}
        {last.payment !== regular &&
          payments.length > 1 &&
          ` Последний — ${money(last.payment)}: в нём учтено округление до рубля.`}
      </p>
    </details>
  );
}
