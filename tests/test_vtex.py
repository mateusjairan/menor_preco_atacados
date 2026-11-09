from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.adapters.vtex import VtexAdapter
from src.config import TIER_A, ChainConfig
from src.http import HttpError

FIXTURE = Path(__file__).parent / "fixtures" / "vtex_search.json"


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def close(self):
        self.closed = True


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _adapter(payload, chain: ChainConfig | None = None):
    client = FakeClient(payload)
    return VtexAdapter(chain or TIER_A[0], client=client), client


def test_parses_available_products(payload):
    adapter, client = _adapter(payload)
    products = adapter.fetch("leite integral", max_pages=1)

    assert len(products) == 4  # café esgotado fica fora
    assert len(client.calls) == 1
    url, params = client.calls[0]
    assert url.endswith("/api/catalog_system/pub/products/search")
    assert params == {"ft": "leite integral", "_from": 0, "_to": 49}


def test_chooses_cheapest_available_seller(payload):
    adapter, _ = _adapter(payload)
    products = adapter.fetch("leite", max_pages=1)
    leite = next(p for p in products if p.ean == "7898939247015")

    # Seller de R$ 5,00 está esgotado; o menor disponível é R$ 7,50.
    assert leite.price == 7.5
    assert leite.list_price == 9.0
    assert leite.unit_price == 7.5
    assert leite.package_unit == "l"
    assert leite.image_url.endswith("leite.jpg")


def test_empty_and_zero_ean_become_none(payload):
    adapter, _ = _adapter(payload)
    products = adapter.fetch("detergente", max_pages=1)
    detergente = next(p for p in products if p.name.startswith("Detergente"))
    sabao = next(p for p in products if p.name.startswith("Sabao"))
    assert detergente.ean is None
    assert sabao.ean is None


def test_link_fallback_uses_link_text(payload):
    adapter, _ = _adapter(payload)
    products = adapter.fetch("arroz", max_pages=1)
    arroz = next(p for p in products if p.name.startswith("Arroz"))
    assert arroz.url == ("https://www.gbarbosa.com.br/arroz-branco-tipo-1-5kg-5721/p")


def test_sold_out_product_is_skipped(payload):
    adapter, _ = _adapter(payload)
    products = adapter.fetch("cafe", max_pages=1)
    assert all(not p.name.startswith("Cafe") for p in products)


def test_no_available_seller_skips_item(payload):
    data = copy.deepcopy(payload)
    for seller in data[0]["items"][0]["sellers"]:
        seller["commertialOffer"]["AvailableQuantity"] = 0
    adapter, _ = _adapter(data)
    products = adapter.fetch("leite", max_pages=1)
    assert all(p.ean != "7898939247015" for p in products)


def test_empty_term_makes_no_request(payload):
    adapter, client = _adapter(payload)
    assert adapter.fetch("   ", max_pages=1) == []
    assert client.calls == []


def test_http_error_propagates(payload):
    adapter, _ = _adapter(HttpError("bloqueio temporário"))
    with pytest.raises(HttpError, match="bloqueio temporário"):
        adapter.fetch("leite", max_pages=1)


def test_invalid_payload_raises_adapter_error(payload):
    adapter, _ = _adapter({"not": "a list"})
    with pytest.raises(Exception, match="resposta inesperada"):
        adapter.fetch("leite", max_pages=1)


def test_close_closes_client(payload):
    adapter, client = _adapter(payload)
    adapter.close()
    assert client.closed is True
