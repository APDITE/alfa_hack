import json

import pytest
from fastapi.testclient import TestClient

import generate
from app.main import app


@pytest.fixture()
def client():
    # with-блок запускает lifespan: данные грузятся, доступность сбрасывается
    with TestClient(app) as c:
        yield c


def test_egrul_contract(client):
    r = client.get("/mock/egrul/7700000001")
    assert r.status_code == 200
    assert set(r.json()) == {"inn", "name", "legal_form", "okved", "registration_date", "region", "status", "director"}
    assert r.json()["status"] == "active"


def test_transparent_business_contract(client):
    r = client.get("/mock/transparent-business/7700000001")
    assert r.status_code == 200
    assert set(r.json()) == {"inn", "revenue_year", "expenses_year", "liabilities_total", "employees", "tax_arrears"}


def test_bki_contract(client):
    r = client.get("/mock/bki/7700000004")
    assert r.status_code == 200
    assert r.json() == {
        "inn": "7700000004", "active_loans": 4, "overdue_count": 4, "max_overdue_days": 120, "total_debt": 10_000_000,
    }


@pytest.mark.parametrize("path", ["egrul", "transparent-business", "bki"])
@pytest.mark.parametrize("inn", ["abc", "12345", "12345678901", "77000000х1"])
def test_malformed_inn_is_404(client, path, inn):
    assert client.get(f"/mock/{path}/{inn}").status_code == 404


def test_unknown_inn_gets_deterministic_synthetic_data(client):
    first = client.get("/mock/egrul/5012345678").json()
    assert first == client.get("/mock/egrul/5012345678").json()
    assert first != client.get("/mock/egrul/5012345679").json()
    assert (first["inn"], first["region"], first["status"], first["legal_form"]) == (
        "5012345678", "50", "active", "OOO",
    )
    assert client.get("/mock/bki/5012345678").json() == client.get("/mock/bki/5012345678").json()


def test_synthetic_values_are_pinned(client):
    # значения зафиксированы: если генератор синтетики изменится, демо у жюри поплывёт
    r = client.get("/mock/egrul/5012345678").json()
    assert (r["name"], r["registration_date"], r["okved"]) == ("ООО «Бриз Лого»", "2018-04-21", "10.71")
    assert client.get("/mock/bki/5012345678").json()["total_debt"] == 1_000_000


def test_synthetic_company_has_no_financials_and_clean_history(client):
    assert client.get("/mock/transparent-business/5012345678").status_code == 404
    bki = client.get("/mock/bki/5012345678").json()
    assert set(bki) == {"inn", "active_loans", "overdue_count", "max_overdue_days", "total_debt"}
    assert bki["max_overdue_days"] < 30


def test_synthetic_individual_entrepreneur_has_12_digit_inn(client):
    r = client.get("/mock/egrul/501234567890").json()
    assert r["legal_form"] == "IP" and r["name"].startswith("ИП ")


def test_synthetic_respects_availability(client):
    client.post("/mock/admin/availability", json={"service": "egrul", "available": False})
    assert client.get("/mock/egrul/5012345678").status_code == 503


def test_synthetic_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MOCKS_SYNTHETIC_UNKNOWN_INN", "0")
    with TestClient(app) as c:
        assert c.get("/mock/egrul/5012345678").status_code == 404
        assert c.get("/mock/egrul/7700000001").status_code == 200


def test_scenario_3_has_no_transparent_business_record(client):
    assert client.get("/mock/egrul/7700000003").status_code == 200
    assert client.get("/mock/transparent-business/7700000003").status_code == 404


def test_demo_registry_matches_backend_seed(client):
    # реквизиты, которые бэкенд сидит из backend/config/demo_companies.yaml
    r = client.get("/mock/egrul/7700000003").json()
    assert (r["name"], r["legal_form"], r["registration_date"], r["region"]) == (
        "ИП Ковалёва Мария Игоревна", "IP", "2021-09-10", "50",
    )
    assert client.get("/mock/egrul/7700000008").json()["registration_date"] == "2026-02-01"


def test_scenario_6_is_liquidating(client):
    assert client.get("/mock/egrul/7700000006").json()["status"] == "liquidating"


@pytest.mark.parametrize(
    ("service", "path"),
    [("egrul", "egrul"), ("transparent_business", "transparent-business"), ("bki", "bki")],
)
def test_availability_switch_gives_503_and_restores(client, service, path):
    url = f"/mock/{path}/7700000001"
    assert client.post("/mock/admin/availability", json={"service": service, "available": False}).status_code == 200
    assert client.get(url).status_code == 503
    # остальные источники продолжают работать
    other = "egrul" if service != "egrul" else "bki"
    assert client.get(f"/mock/{other}/7700000001").status_code == 200
    client.post("/mock/admin/availability", json={"service": service, "available": True})
    assert client.get(url).status_code == 200


def test_503_wins_over_404_for_disabled_service(client):
    client.post("/mock/admin/availability", json={"service": "bki", "available": False})
    assert client.get("/mock/bki/abc").status_code == 503


def test_availability_rejects_unknown_service(client):
    assert client.post("/mock/admin/availability", json={"service": "x", "available": False}).status_code == 422


def test_availability_resets_on_restart():
    with TestClient(app) as c:
        c.post("/mock/admin/availability", json={"service": "bki", "available": False})
    with TestClient(app) as c:
        assert c.get("/mock/admin/availability").json()["bki"] is True


# ---- генератор ----


def test_generation_is_reproducible():
    assert generate.render(generate.generate()) == generate.render(generate.generate())


def test_committed_file_matches_generator():
    committed = generate.DEFAULT_OUT.read_bytes().decode("utf-8")
    assert committed == generate.render(generate.generate()), "run: uv run python generate.py"


def test_dataset_shape():
    companies = json.loads(generate.DEFAULT_OUT.read_text(encoding="utf-8"))
    demos = [c for c in companies if c["demo"]]
    assert [c["inn"] for c in demos] == [f"770000000{i}" for i in range(1, 9)]
    assert [c["demo"]["scenarios"] for c in demos] == [[1, 7], [2], [3], [4], [5], [6], [8], [11]]
    assert 150 <= len(companies) - len(demos) <= 200
    inns = [c["inn"] for c in companies]
    assert len(inns) == len(set(inns))
    for c in companies:
        assert c["legal_form"] in {"OOO", "IP"}
        assert c["status"] in {"active", "liquidating", "liquidated"}
        if not c["demo"]:  # демо-ИП живут с 10-значными ИНН по договору docs/scenarios.md
            assert len(c["inn"]) == (10 if c["legal_form"] == "OOO" else 12)
