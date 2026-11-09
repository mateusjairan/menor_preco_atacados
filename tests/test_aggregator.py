from __future__ import annotations

import pytest

from src import config
from src.adapters.base import Adapter, AdapterError
from src.aggregator import (
    backfill_package_sizes,
    build_adapters,
    rank,
    search,
    sort_products,
)
from src.models import ChainResult


class FakeAdapter(Adapter):
    def __init__(self, name, slug, products=None, error=None):
        config_chain = config.ChainConfig(name, slug, "https://example.test", "public")
        super().__init__(config_chain)
        self._products = products or []
        self._error = error
        self.closed = False

    def fetch(self, term, max_pages=None):
        if self._error:
            raise AdapterError(self._error)
        return self._products

    def close(self):
        self.closed = True


def test_one_failure_does_not_break_others(make_product):
    good = FakeAdapter("GBarbosa", "gbarbosa", products=[make_product()], error=None)
    bad = FakeAdapter("Atacadão", "atacadao", error="bloqueio temporário")

    results = search("leite", adapters=[good, bad])

    assert [result.chain for result in results] == ["GBarbosa", "Atacadão"]
    assert results[0].error is None
    assert len(results[0].products) == 1
    assert results[1].error == "bloqueio temporário"
    assert good.closed is True
    assert bad.closed is True


def test_unexpected_exception_is_friendly():
    class Exploding(FakeAdapter):
        def fetch(self, term, max_pages=None):
            raise RuntimeError("boom")

    exploding = Exploding("Hiperideal", "hiperideal")
    results = search("leite", adapters=[exploding])
    assert results[0].error == "resposta inesperada"


def test_empty_term_returns_empty():
    assert search("   ", adapters=[]) == []


def test_build_adapters_default_is_tier_a_only(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REVERSE_API", False)
    adapters = build_adapters(include_reverse=True)
    assert len(adapters) == 5
    assert all(adapter.chain.access == "public" for adapter in adapters)


def test_build_adapters_reverse_only_when_flag_enabled(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REVERSE_API", True)
    adapters = build_adapters(include_reverse=True)
    assert len(adapters) == 8
    assert [a.slug for a in adapters[-3:]] == ["pinheiro", "nordestao", "diniz"]


def test_chain_filter():
    adapters = build_adapters(chain_slugs=["gbarbosa", "treichel"])
    assert [adapter.slug for adapter in adapters] == ["gbarbosa", "treichel"]


def test_rank_picks_best_unit_price(make_product):
    cheap_small = make_product(
        name="Leite 500ml",
        price=4.0,
        package_size=0.5,
        package_unit="l",
        chain="GBarbosa",
        chain_slug="gbarbosa",
    )
    expensive_big = make_product(
        name="Leite 1l",
        price=10.0,
        package_size=1.0,
        package_unit="l",
        chain="Atacadão",
        chain_slug="atacadao",
    )
    results = [
        ChainResult("GBarbosa", [cheap_small]),
        ChainResult("Atacadão", [expensive_big]),
    ]

    ranking = rank(results)

    assert ranking.best_overall is cheap_small
    assert ranking.worst_overall is expensive_big
    assert ranking.best_by_chain["GBarbosa"] is cheap_small
    assert ranking.best_by_chain["Atacadão"] is expensive_big
    assert ranking.savings_pct == pytest.approx(0.2)
    # Tamanhos diferentes não formam grupo: não há economia "justa".
    assert ranking.comparable_savings_pct is None


def test_rank_comparable_savings_for_same_product(make_product):
    cheap = make_product(chain="GBarbosa", chain_slug="gbarbosa", price=5.0)
    expensive = make_product(chain="Atacadão", chain_slug="atacadao", price=10.0)

    ranking = rank(
        [ChainResult("GBarbosa", [cheap]), ChainResult("Atacadão", [expensive])]
    )

    assert ranking.best_overall is cheap
    assert ranking.comparable_worst is expensive
    assert ranking.comparable_savings_pct == pytest.approx(0.5)


def test_rank_without_units_has_no_overall(make_product):
    product = make_product(package_size=None, package_unit=None)
    ranking = rank([ChainResult("GBarbosa", [product])])
    assert ranking.best_overall is None
    assert ranking.savings_pct is None
    assert ranking.best_by_chain["GBarbosa"] is product


def test_sort_products_unitless_last(make_product):
    unitless = make_product(
        name="Sem tamanho", package_size=None, package_unit=None, price=1.0
    )
    expensive = make_product(name="Leite 1l", price=10.0)
    cheap = make_product(name="Leite 500ml", price=3.0, package_size=0.5)

    ordered = sort_products([unitless, expensive, cheap])
    assert ordered == [cheap, expensive, unitless]


def test_backfill_package_size_by_ean(make_product):
    unknown = make_product(
        chain="Hiperideal",
        chain_slug="hiperideal",
        name="Cerveja Budweiser Multipack LT 350ml",
        ean="7891991308670",
        price=38.28,
        package_size=None,
        package_unit=None,
    )
    known = make_product(
        chain="GBarbosa",
        chain_slug="gbarbosa",
        name="Cerveja Budweiser Lata 350ml com 12 Unidades",
        ean="7891991308670",
        price=44.28,
        package_size=4.2,
        package_unit="l",
    )

    results = backfill_package_sizes(
        [ChainResult("GBarbosa", [known]), ChainResult("Hiperideal", [unknown])]
    )
    fixed = results[1].products[0]

    assert fixed.package_size == 4.2
    assert fixed.package_unit == "l"
    assert fixed.unit_price == pytest.approx(38.28 / 4.2)


def test_backfill_never_overrides_known_size(make_product):
    left = make_product(ean="123", package_size=4.2, package_unit="l")
    right = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        ean="123",
        package_size=0.35,
        package_unit="l",
    )
    results = backfill_package_sizes(
        [ChainResult("GBarbosa", [left]), ChainResult("Atacadão", [right])]
    )
    assert results[0].products[0].package_size == 4.2
    assert results[1].products[0].package_size == 0.35


def test_error_only_result_is_preserved():
    result = ChainResult("Mercantil", error="tempo esgotado", elapsed_ms=12000)
    results = search(
        "leite", adapters=[FakeAdapter("Mercantil", "mercantil", error=result.error)]
    )
    assert results[0].error == "tempo esgotado"
    assert results[0].products == []
