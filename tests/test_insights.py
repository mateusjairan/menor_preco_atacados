from __future__ import annotations

from src.aggregator import Ranking
from src.insights import (
    build_market_summary,
    chain_comparison,
    format_brl,
    format_pct,
    market_insights,
    reference_group,
)
from src.matching import group_products
from src.models import ChainResult


def test_format_brl_and_pct():
    assert format_brl(4.5) == "R$ 4,50"
    assert format_brl(None) == "—"
    assert format_pct(0.53) == "53%"
    assert format_pct(None) == "—"


def test_build_market_summary(make_product):
    products = [
        make_product(price=5.0),
        make_product(name="Sem tamanho", package_size=None, package_unit=None),
    ]
    results = [
        ChainResult("GBarbosa", products=products),
        ChainResult("Atacadão", error="tempo esgotado"),
    ]

    summary = build_market_summary(results, products)

    assert summary.total_products == 2
    assert summary.comparable_products == 1
    assert summary.missing_size == 1
    assert summary.chains_with_results == 1
    assert summary.chains_total == 2
    assert summary.errors == 1
    assert summary.collected_at is not None


def test_reference_group_and_chain_comparison(make_product):
    cheap = make_product(
        chain="GBarbosa",
        chain_slug="gbarbosa",
        ean="123",
        price=5.0,
        package_size=1.0,
        package_unit="l",
    )
    expensive = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        ean="123",
        price=10.0,
        package_size=1.0,
        package_unit="l",
    )
    duplicate = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        ean="123",
        price=8.0,
        package_size=1.0,
        package_unit="l",
    )
    groups = group_products([cheap, expensive, duplicate])
    group = reference_group(groups, cheap)

    assert group is not None
    comparison = chain_comparison(group)

    assert [offer.chain for offer in comparison] == ["GBarbosa", "Atacadão"]
    assert comparison[0].unit_price == 5.0
    assert comparison[1].unit_price == 8.0


def test_market_insights_are_generated_from_data(make_product):
    best = make_product(
        chain="GBarbosa",
        chain_slug="gbarbosa",
        ean="123",
        price=5.0,
        package_size=1.0,
        package_unit="l",
    )
    worst = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        ean="123",
        price=10.0,
        package_size=1.0,
        package_unit="l",
    )
    groups = group_products([best, worst])
    group = reference_group(groups, best)
    comparison = chain_comparison(group)
    results = [
        ChainResult("GBarbosa", [best]),
        ChainResult("Atacadão", [worst]),
    ]
    summary = build_market_summary(results, [best, worst], groups)
    ranking = Ranking(
        best_by_chain={"GBarbosa": best, "Atacadão": worst},
        best_overall=best,
        worst_overall=worst,
        savings_pct=0.5,
        comparable_worst=worst,
        comparable_savings_pct=0.5,
    )

    insights = market_insights(ranking, summary, comparison)

    assert any("GBarbosa lidera" in line for line in insights)
    assert any("Atacadão" in line and "50%" in line for line in insights)
    assert any("2 itens coletados" in line for line in insights)


def test_insights_when_no_unit_price(make_product):
    product = make_product(
        name="Sem tamanho",
        package_size=None,
        package_unit=None,
    )
    summary = build_market_summary([ChainResult("GBarbosa", [product])], [product])
    ranking = Ranking({}, None, None, None)

    insights = market_insights(ranking, summary, [])

    assert any("não pôde ser calculado" in line for line in insights)
    assert any("1 item" in line or "1 itens" in line for line in insights)
