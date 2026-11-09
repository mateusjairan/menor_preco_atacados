from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

import src.aggregator as aggregator
from src.models import ChainResult, Product

APP = Path(__file__).resolve().parents[1] / "app.py"


def _fake_search(term, chain_slugs=None, include_reverse=False):
    product = Product(
        chain="GBarbosa",
        chain_slug="gbarbosa",
        name="Leite Integral 1l",
        brand="Marca",
        ean="7891000",
        price=5.0,
        list_price=6.0,
        package_size=1.0,
        package_unit="l",
        unit_price=5.0,
        url="https://example.test/leite/p",
        image_url=None,
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        access="public",
    )
    return [ChainResult("GBarbosa", products=[product], elapsed_ms=120)]


def test_app_starts_without_exception(monkeypatch):
    monkeypatch.setattr(aggregator, "search", _fake_search)
    at = AppTest.from_file(str(APP), default_timeout=30).run()

    assert not at.exception
    assert at.title[0].value == "Radar de Preço NE"
    assert any("Buscar" in button.label for button in at.button)


def test_app_search_renders_results(monkeypatch):
    monkeypatch.setattr(aggregator, "search", _fake_search)
    at = AppTest.from_file(str(APP), default_timeout=30).run()

    at.text_input(key="termo").set_value("leite")
    at.button(key="buscar").click()
    at.run()

    assert not at.exception
    assert at.dataframe, "tabela de resultados não foi renderizada"
    table = at.dataframe[0].value
    assert "Preço/un" not in table.columns
    assert "Preço" in table.columns
    assert any("Leitura do mercado" in str(element.value) for element in at.markdown)
