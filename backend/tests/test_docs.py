"""Generated docs stay in sync with the code."""

from pathlib import Path

from app.docgen import data_model, state_diagram

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_state_diagram_matches_the_code() -> None:
    committed = (DOCS / "state-diagram.md").read_text(encoding="utf-8")
    assert committed == state_diagram(), "statuses changed: run `make docs` and commit docs/"


def test_data_model_lists_every_table() -> None:
    text = data_model()
    for table in ("applications", "status_history", "pipeline_jobs", "feed_items"):
        assert f"    {table} {{" in text
    assert 'status_history }o--|| applications : "application_id"' in text
