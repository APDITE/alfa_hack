import type { PaymentSchedule } from "../api/types";
import { money, plural } from "../utils/format";

type Props = {
  schedule: PaymentSchedule;
  /** Open where the client confirms they have read it (signing). */
  open?: boolean;
};

/** Monthly payments for the offered or signed terms, as calculated by the bank. */
export default function PaymentScheduleView({ schedule, open = false }: Props) {
  const { payments, total_paid: totalPaid, overpayment } = schedule;
  if (payments.length === 0) return null;
  const regular = payments[0].payment;
  const last = payments[payments.length - 1];

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
              <td>{money(totalPaid)}</td>
              <td>{money(totalPaid - overpayment)}</td>
              <td>{money(overpayment)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="schedule__note muted small">
        Платёж раз в месяц, первый — через месяц после выдачи.
        {last.payment !== regular &&
          ` Последний — ${money(last.payment)}: в нём учтено округление до рубля.`}
      </p>
    </details>
  );
}
