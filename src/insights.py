"""Leitura de mercado derivada dos dados da busca, sem números inventados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .matching import (
    ProductGroup,
    group_products,
    similar_group_count,
)
from .models import ChainResult, Product
from .units import format_unit_price


def format_brl(value: float | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}%"


@dataclass(frozen=True)
class ChainOffer:
    chain: str
    product: Product
    unit_price: float


@dataclass(frozen=True)
class MarketSummary:
    total_products: int
    comparable_products: int
    missing_size: int
    chains_with_results: int
    chains_total: int
    errors: int
    similar_groups: int
    collected_at: datetime | None


def build_market_summary(
    results: list[ChainResult],
    products: list[Product],
    groups: list[ProductGroup] | None = None,
) -> MarketSummary:
    if groups is None:
        groups = group_products(products)
    dates = [product.collected_at for product in products]
    return MarketSummary(
        total_products=len(products),
        comparable_products=sum(
            1 for product in products if product.unit_price is not None
        ),
        missing_size=sum(1 for product in products if product.unit_price is None),
        chains_with_results=sum(1 for result in results if result.products),
        chains_total=len(results),
        errors=sum(1 for result in results if result.error),
        similar_groups=similar_group_count(groups),
        collected_at=max(dates) if dates else None,
    )


def reference_group(
    groups: list[ProductGroup], best: Product | None
) -> ProductGroup | None:
    if best is None:
        return None
    return next(
        (
            group
            for group in groups
            if any(product is best for product in group.products)
        ),
        None,
    )


def chain_comparison(group: ProductGroup | None) -> list[ChainOffer]:
    """Melhor oferta de cada rede dentro do mesmo grupo, ordenada por preço/un."""

    if group is None:
        return []

    by_chain: dict[str, ChainOffer] = {}
    for product in group.products:
        if product.unit_price is None:
            continue
        offer = ChainOffer(product.chain, product, product.unit_price)
        current = by_chain.get(product.chain)
        if current is None or (offer.unit_price, offer.product.price) < (
            current.unit_price,
            current.product.price,
        ):
            by_chain[product.chain] = offer

    return sorted(
        by_chain.values(),
        key=lambda offer: (offer.unit_price, offer.product.price),
    )


def market_insights(
    ranking,
    summary: MarketSummary,
    comparison: list[ChainOffer],
) -> list[str]:
    insights: list[str] = []
    best = ranking.best_overall

    if best is None:
        insights.append(
            "Nenhum item desta busca teve tamanho identificado; o ranking por "
            "unidade não pôde ser calculado."
        )
    else:
        insights.append(
            f"{best.chain} lidera em {best.name} com "
            f"{format_unit_price(best.unit_price, best.package_unit)}."
        )
        if len(comparison) >= 2:
            second = comparison[1]
            if second.unit_price > 0:
                gap = 1 - (comparison[0].unit_price / second.unit_price)
                insights.append(
                    f"O segundo colocado, {second.chain}, está "
                    f"{format_pct(gap)} acima no mesmo produto/tamanho."
                )
        else:
            insights.append(
                "Não há outro preço comparável do mesmo produto/tamanho nesta busca."
            )

    count = summary.total_products
    noun = "item" if count == 1 else "itens"
    verb = "coletado" if count == 1 else "coletados"
    coverage = (
        f"{count} {noun} {verb} em "
        f"{summary.chains_with_results} de {summary.chains_total} redes"
    )
    if summary.errors:
        failure = "falhou" if summary.errors == 1 else "falharam"
        coverage += f"; {summary.errors} {failure}"
    insights.append(coverage + ".")

    quality: list[str] = []
    if summary.missing_size:
        quality.append(f"{summary.missing_size} sem tamanho identificado")
    if summary.similar_groups:
        quality.append(f"{summary.similar_groups} com nome aproximado")
    if quality:
        insights.append("Qualidade dos dados: " + " e ".join(quality) + ".")

    return insights
