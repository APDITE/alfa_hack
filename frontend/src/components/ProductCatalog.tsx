import { useEffect, useState } from "react";

import { api, errorText } from "../api/client";
import type { LoanTerms, Product, PurposeCategory, Recommendation } from "../api/types";
import { money, percent } from "../utils/format";
import { PURPOSE_LABELS } from "../utils/labels";
import PreapprovedOffers from "./PreapprovedOffers";

export type Preset = { amount: number; term_months: number };

type Props = {
  /** Pre-approved offers of the bank, shown above the catalog. */
  offers: LoanTerms[];
  onApply: (product: Product, purpose: PurposeCategory | null, preset?: Preset) => void;
};

const PURPOSES: PurposeCategory[] = ["inventory", "cash_gap", "equipment", "other"];

export default function ProductCatalog({ offers, onApply }: Props) {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [purpose, setPurpose] = useState<PurposeCategory | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .products()
      .then(setProducts)
      .catch((caught: unknown) => setError(errorText(caught)));
  }, []);

  async function choosePurpose(value: PurposeCategory) {
    setPurpose(value);
    setError("");
    try {
      setRecommendation(await api.recommend(value));
    } catch (caught) {
      setRecommendation(null);
      setError(errorText(caught));
    }
  }

  const recommendedId = recommendation?.product.id;

  function applyOffer(offer: LoanTerms) {
    const product = products?.find((p) => p.id === offer.product_id);
    if (product) onApply(product, null, { amount: offer.amount, term_months: offer.term_months });
  }

  return (
    <section className="card">
      <h2>Кредитные продукты</h2>

      <PreapprovedOffers offers={products ? offers : []} onApply={applyOffer} />

      <div className="advisor">
        <h3>На что нужны деньги?</h3>
        <p className="muted">Ответьте на один вопрос — подскажем подходящий продукт.</p>
        <div className="chips" role="group" aria-label="Цель кредита">
          {PURPOSES.map((value) => (
            <button
              key={value}
              type="button"
              className={`chip${purpose === value ? " chip--active" : ""}`}
              aria-pressed={purpose === value}
              onClick={() => void choosePurpose(value)}
            >
              {PURPOSE_LABELS[value]}
            </button>
          ))}
        </div>
        {recommendation && (
          <div className="advisor__answer" role="status">
            <strong>Вам подойдёт: {recommendation.product.name}.</strong> {recommendation.reason}
          </div>
        )}
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!products && !error && <p className="muted">Загружаем продукты…</p>}

      <div className="product-list">
        {products?.map((product) => (
          <article
            key={product.id}
            className={`product-card${recommendedId === product.id ? " product-card--recommended" : ""}`}
          >
            {recommendedId === product.id && <span className="product-card__tag">Подходит вам</span>}
            <h3>{product.name}</h3>
            <p className="product-card__description">{product.description}</p>
            <dl className="facts">
              <dt>Сумма</dt>
              <dd>
                {money(product.min_amount)} – {money(product.max_amount)}
              </dd>
              <dt>Срок</dt>
              <dd>
                {product.min_term_months}–{product.max_term_months} мес.
              </dd>
              <dt>Ставка</dt>
              <dd>от {percent(product.base_rate)} годовых</dd>
              <dt>Бизнесу</dt>
              <dd>от {product.min_business_age_months} мес.</dd>
            </dl>
            <button
              type="button"
              className="button button--primary"
              onClick={() =>
                onApply(
                  product,
                  purpose !== null && product.purposes.includes(purpose) ? purpose : null,
                )
              }
            >
              Оформить заявку
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
