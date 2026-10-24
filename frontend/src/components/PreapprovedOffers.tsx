import type { LoanTerms } from "../api/types";
import { money, percent } from "../utils/format";
import { PRODUCT_NAMES } from "../utils/labels";

type Props = {
  offers: LoanTerms[];
  onApply: (offer: LoanTerms) => void;
};

/** What the bank approves automatically right now: the same data and rules as the pipeline. */
export default function PreapprovedOffers({ offers, onApply }: Props) {
  if (offers.length === 0) return null;
  return (
    <section className="preapproved" aria-labelledby="preapproved-title">
      <div className="preapproved__head">
        <span className="badge badge--success">Предварительно одобрено</span>
        <h3 id="preapproved-title">Банк уже проверил вашу компанию</h3>
        <p className="muted">
          По данным ЕГРЮЛ, «Прозрачного бизнеса» и бюро кредитных историй на сегодня. Заявку на эти
          условия банк одобрит автоматически, если данные компании не изменятся.
        </p>
      </div>
      <ul className="preapproved__list">
        {offers.map((offer) => (
          <li key={offer.product_id} className="preapproved__offer">
            <div className="preapproved__terms">
              <span className="preapproved__product">{PRODUCT_NAMES[offer.product_id]}</span>
              <strong className="preapproved__amount">до {money(offer.amount)}</strong>
              <span className="muted">
                на {offer.term_months} мес. · {percent(offer.rate)} годовых · платёж{" "}
                {money(offer.monthly_payment)} в месяц
              </span>
            </div>
            <button type="button" className="button button--primary" onClick={() => onApply(offer)}>
              Оформить
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
