
import { useState } from "react";
import CreditApplicationForm from "./CreditApplicationForm";
import MyApplications from "./MyApplications";
import type { CreditApplication } from "../types/application";

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
  const [showApplications, setShowApplications] = useState(false);
  const [editingApplication, setEditingApplication] =
  useState<CreditApplication | null>(null);
  if (editingApplication) {
  return (
    <CreditApplicationForm
      key={editingApplication.id}
      productName={editingApplication.productName}
      application={editingApplication}
      onClose={() => {
        setEditingApplication(null);
        setShowApplications(true);
      }}
    />
  );
 }
  if (showApplications) {
  return (
    <div>
      <button
        type="button"
        className="catalog-navigation-button"
        onClick={() => setShowApplications(false)}
        >
        К кредитным продуктам
      </button>
      <MyApplications
    onEdit={(application) => {
    setEditingApplication(application);
    setShowApplications(false);
  }}
/>
    </div>
  );
 }
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
      <button
        type="button"
        className="catalog-navigation-button"
        onClick={() => setShowApplications(true)}
        >
        Мои заявки 
      </button>

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
