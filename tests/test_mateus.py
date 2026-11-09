from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config
from src.adapters.base import AdapterError
from src.adapters.mateus import MateusAdapter, _measure_package

FIXTURES = Path(__file__).parent / "fixtures"
CHAIN = next(chain for chain in config.TIER_B if chain.slug == "mateus")


class FakeClient:
    def __init__(self, markets, search):
        self.markets = markets
        self.search = search
        self.get_calls = []
        self.post_calls = []
        self.closed = False

    def get_json(self, url, params=None):
        self.get_calls.append((url, params))
        return self.markets

    def post_json(self, url, body, params=None):
        self.post_calls.append((url, body, params))
        return self.search

    def close(self):
        self.closed = True


def _client():
    markets = json.loads((FIXTURES / "mateus_markets.json").read_text("utf-8"))
    search = json.loads((FIXTURES / "mateus_search.json").read_text("utf-8"))
    return FakeClient(markets, search)


def test_resolves_first_online_market_and_parses_products():
    client = _client()
    adapter = MateusAdapter(CHAIN, client=client)

    products = adapter.fetch("leite", max_pages=1)

    assert adapter.market_id == "market-1"
    assert len(client.get_calls) == 1
    assert len(client.post_calls) == 1
    assert len(products) == 3  # esgotado e fora de venda ficam fora
    assert {p.name for p in products} == {
        "Leite em Pó Integral Piracanjuba 200g",
        "Leite Longa Vida Natville Integral 1L",
        "Refrigerante Coca-Cola 2L",
    }

    leite_po = next(p for p in products if p.ean == "7898215152330")
    assert leite_po.chain == "Grupo Mateus"
    assert leite_po.price == 6.79
    assert leite_po.list_price == 7.39
    assert leite_po.package_size == 0.2
    assert leite_po.package_unit == "kg"
    assert leite_po.unit_price == pytest.approx(33.95)
    assert leite_po.url == ("https://www.mateusmais.com.br/produtos/market-1/produto-1")
    assert leite_po.image_url.endswith("leite-em-po.png")

    refrigerante = next(p for p in products if p.name.startswith("Refrigerante"))
    assert refrigerante.package_size == 2.0
    assert refrigerante.package_unit == "l"


def test_search_body_filters_market_and_for_sale():
    client = _client()
    adapter = MateusAdapter(CHAIN, client=client)

    adapter.fetch("leite", max_pages=1)

    url, body, _ = client.post_calls[0]
    assert url.endswith("/api/products/internal/v1/service/priority")
    assert body["service"] == "meilisearch"
    assert body["market_priority"] == {"market_ids": ["market-1"]}
    assert "market_id%3Amarket-1" in body["params"]
    assert "for_sale%3Atrue" in body["params"]


def test_explicit_market_skips_market_lookup():
    client = _client()
    adapter = MateusAdapter(CHAIN, client=client, market_id="market-1")

    products = adapter.fetch("leite", max_pages=1)

    assert client.get_calls == []
    assert len(products) == 3


def test_empty_term_makes_no_request():
    client = _client()
    adapter = MateusAdapter(CHAIN, client=client)

    assert adapter.fetch("   ", max_pages=1) == []
    assert client.get_calls == []
    assert client.post_calls == []


def test_invalid_payload_raises_adapter_error():
    client = _client()
    client.search = {"not": "hits"}
    adapter = MateusAdapter(CHAIN, client=client, market_id="market-1")

    with pytest.raises(AdapterError, match="resposta inesperada"):
        adapter.fetch("leite", max_pages=1)


@pytest.mark.parametrize(
    ("measure", "measure_type", "expected"),
    [
        (200, "G", (0.2, "kg")),
        (1, "KG", (1.0, "kg")),
        (500, "ML", (0.5, "l")),
        (2, "L", (2.0, "l")),
        (30, "UN", (30.0, "un")),
        (None, "G", (None, None)),
    ],
)
def test_measure_package(measure, measure_type, expected):
    assert _measure_package(measure, measure_type) == expected


def test_close_closes_client():
    client = _client()
    adapter = MateusAdapter(CHAIN, client=client, market_id="market-1")
    adapter.close()
    assert client.closed is True
