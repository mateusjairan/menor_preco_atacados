from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config
from src.adapters.base import AdapterError
from src.adapters.vipcommerce import VipCommerceAdapter

FIXTURES = Path(__file__).parent / "fixtures"
CHAIN = next(chain for chain in config.TIER_B if chain.slug == "villefort")


class FakeClient:
    def __init__(self, domain, login, search):
        self.domain = domain
        self.login = login
        self.search = search
        self.get_calls = []
        self.post_calls = []
        self.headers = {}
        self.closed = False

    def get_json(self, url, params=None):
        self.get_calls.append((url, params))
        if "organizacoes/filiais/dominio" in url:
            return self.domain
        return self.search

    def post_json(self, url, body, params=None):
        self.post_calls.append((url, body, params))
        return self.login

    def close(self):
        self.closed = True


def _client():
    domain = json.loads((FIXTURES / "vipcommerce_domain.json").read_text("utf-8"))
    login = json.loads((FIXTURES / "vipcommerce_login.json").read_text("utf-8"))
    search = json.loads((FIXTURES / "vipcommerce_search.json").read_text("utf-8"))
    return FakeClient(domain, login, search)


def test_fetches_and_parses_products(monkeypatch):
    monkeypatch.setattr(config, "VIPCOMMERCE_LOJA_KEY", "chave-de-teste")
    client = _client()
    adapter = VipCommerceAdapter(CHAIN, client=client)

    products = adapter.fetch("leite", max_pages=1)

    assert len(products) == 2  # indisponível fica fora
    assert len(client.get_calls) == 2  # domínio + busca
    assert len(client.post_calls) == 1
    assert client.post_calls[0][1]["domain"] == "villefortentrega.com.br"
    assert client.headers["OrganizationId"] == "120"
    assert client.headers["DomainKey"] == "villefortentrega.com.br"
    assert client.headers["Authorization"].startswith("Bearer ")

    leite = next(p for p in products if p.package_unit == "l")
    assert leite.price == 4.58
    assert leite.unit_price == 4.58
    assert leite.ean == "7896122305207"
    assert leite.url.endswith("/produto/1255/leite-integral-longa-vida-porto-alegre-1l")

    pack = next(
        p
        for p in products
        if p.package_size is not None and abs(p.package_size - 0.45) < 1e-9
    )
    assert pack.package_unit == "kg"
    assert pack.price == 12.0
    assert pack.unit_price == pytest.approx(26.6667, rel=1e-3)
    assert pack.brand == "ITAMBÉ"
    assert pack.image_url.endswith("99beb9b6-f45b-4f90-a88a-ca1a04e5d555.jpg")


def test_requires_loja_key(monkeypatch):
    monkeypatch.setattr(config, "VIPCOMMERCE_LOJA_KEY", "")
    adapter = VipCommerceAdapter(CHAIN, client=_client())

    with pytest.raises(AdapterError, match="VIPCOMMERCE_LOJA_KEY"):
        adapter.fetch("leite", max_pages=1)


def test_requires_base_url():
    chain = next(chain for chain in config.TIER_B if chain.slug == "pinheiro")
    adapter = VipCommerceAdapter(chain, client=_client())

    with pytest.raises(AdapterError, match="sem catálogo"):
        adapter.fetch("leite", max_pages=1)


def test_empty_term_makes_no_request():
    client = _client()
    adapter = VipCommerceAdapter(CHAIN, client=client)

    assert adapter.fetch("   ", max_pages=1) == []
    assert client.get_calls == []
    assert client.post_calls == []


def test_close_closes_client():
    client = _client()
    adapter = VipCommerceAdapter(CHAIN, client=client)
    adapter.close()
    assert client.closed is True


def test_reverse_api_is_enabled_by_default():
    assert config.ENABLE_REVERSE_API is True


def test_reverse_adapters_are_not_built_when_flag_is_off(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REVERSE_API", False)
    from src.aggregator import build_adapters

    adapters = build_adapters(include_reverse=True)
    assert all(adapter.chain.access == "public" for adapter in adapters)
