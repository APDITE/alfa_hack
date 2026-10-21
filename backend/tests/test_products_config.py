from pathlib import Path

import pytest
from app.products import ProductsConfigError, load_products

CONFIG = Path(__file__).parent.parent / "config" / "products.yaml"


def test_real_config_loads() -> None:
    products = load_products(CONFIG)
    assert set(products) == {"working_capital", "equipment"}
    for product in products.values():
        p = product.params
        assert p.approve_max_pd < p.reject_min_pd
        assert set(p.risk_premium) == {"low", "medium", "high"}


def test_same_pd_differs_by_product() -> None:
    """Scenario 8 relies on equipment being stricter than working capital."""
    products = load_products(CONFIG)
    pd = 0.10
    assert pd <= products["working_capital"].params.approve_max_pd
    assert pd > products["equipment"].params.approve_max_pd


def test_invalid_thresholds_are_rejected(tmp_path: Path) -> None:
    text = CONFIG.read_text(encoding="utf-8").replace("approve_max_pd: 0.12", "approve_max_pd: 0.9")
    path = tmp_path / "products.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ProductsConfigError):
        load_products(path)


def test_missing_field_is_rejected(tmp_path: Path) -> None:
    text = CONFIG.read_text(encoding="utf-8").replace("    max_debt_load: 0.5\n", "")
    path = tmp_path / "products.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ProductsConfigError, match="max_debt_load"):
        load_products(path)
