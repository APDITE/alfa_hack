"""Load credit products and decision thresholds from `config/products.yaml`."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import Depends, Request

from app.credit_decision import ProductParams

_PARAM_FIELDS = (
    "min_amount",
    "max_amount",
    "min_term_months",
    "max_term_months",
    "base_rate",
    "min_business_age_months",
    "max_debt_load",
    "approve_max_pd",
    "reject_min_pd",
    "max_auto_amount",
)


class ProductsConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ProductConfig:
    """A product as configured: decision parameters plus texts for the catalog."""

    params: ProductParams
    name: str
    description: str
    purposes: tuple[str, ...]


def _parse_product(raw: dict[str, Any]) -> ProductConfig:
    product_id = raw.get("id")
    if not product_id:
        raise ProductsConfigError("Product without id")
    missing = [f for f in ("name", "description", "purposes", *_PARAM_FIELDS) if f not in raw]
    if missing:
        raise ProductsConfigError(f"Product {product_id}: missing fields {missing}")

    params = ProductParams(
        id=str(product_id),
        min_amount=int(raw["min_amount"]),
        max_amount=int(raw["max_amount"]),
        min_term_months=int(raw["min_term_months"]),
        max_term_months=int(raw["max_term_months"]),
        base_rate=float(raw["base_rate"]),
        min_business_age_months=int(raw["min_business_age_months"]),
        max_debt_load=float(raw["max_debt_load"]),
        approve_max_pd=float(raw["approve_max_pd"]),
        reject_min_pd=float(raw["reject_min_pd"]),
        max_auto_amount=int(raw["max_auto_amount"]),
        risk_premium={str(k): float(v) for k, v in (raw.get("risk_premium") or {}).items()},
    )
    if params.min_amount > params.max_amount:
        raise ProductsConfigError(f"Product {product_id}: min_amount > max_amount")
    if params.min_term_months > params.max_term_months:
        raise ProductsConfigError(f"Product {product_id}: min_term_months > max_term_months")
    if not 0 <= params.approve_max_pd < params.reject_min_pd <= 1:
        raise ProductsConfigError(
            f"Product {product_id}: need 0 <= approve_max_pd < reject_min_pd <= 1"
        )
    return ProductConfig(
        params=params,
        name=str(raw["name"]).strip(),
        description=str(raw["description"]).strip(),
        purposes=tuple(str(p) for p in raw["purposes"]),
    )


def load_products(path: Path) -> dict[str, ProductConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    products = [_parse_product(raw) for raw in data.get("products", [])]
    if not products:
        raise ProductsConfigError(f"No products in {path}")
    result = {p.params.id: p for p in products}
    if len(result) != len(products):
        raise ProductsConfigError("Duplicate product ids")
    return result


def get_products(request: Request) -> dict[str, ProductConfig]:
    products: dict[str, ProductConfig] = request.app.state.products
    return products


ProductsDep = Annotated[dict[str, ProductConfig], Depends(get_products)]
