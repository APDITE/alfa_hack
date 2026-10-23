
import { useState } from "react";
import CreditApplicationForm from "./CreditApplicationForm";

type Product = {
  id: string;
  name: string;
  description: string;
};

const products: Product[] = [
  {
    id: "working-capital",
    name: "Оборотный кредит",
    description: "Для закупки товаров и текущих расходов бизнеса.",
  },
  {
    id: "investment",
    name: "Инвестиционный кредит",
    description: "Для покупки оборудования и развития бизнеса.",
  },
];

export default function ProductCatalog() {
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  if (selectedProduct) {
    return (
      <CreditApplicationForm
        productName={selectedProduct.name}
        onClose={() => setSelectedProduct(null)}
      />
    );
  }

  return (
    <section>
      <h2>Кредитные продукты</h2>
      <p>Выберите подходящий вариант финансирования.</p>

      <div className="product-list">
        {products.map((product) => (
          <article className="product-card" key={product.id}>
            <h3>{product.name}</h3>
            <p>{product.description}</p>
            <button
              type="button"
              onClick={() => setSelectedProduct(product)}
            >
              Оформить заявку
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
