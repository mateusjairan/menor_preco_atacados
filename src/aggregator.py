"""Orquestra as redes em paralelo e calcula o ranking justo."""

from __future__ import annotations

import contextlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, replace
from time import perf_counter

from . import config
from .adapters.base import Adapter, AdapterError
from .adapters.mateus import MateusAdapter
from .adapters.vipcommerce import VipCommerceAdapter
from .adapters.vtex import VtexAdapter
from .http import HttpError
from .matching import group_products
from .models import ChainResult, Product
from .units import compute_unit_price

logger = logging.getLogger(__name__)


@dataclass
class Ranking:
    best_by_chain: dict[str, Product]
    best_overall: Product | None
    worst_overall: Product | None
    savings_pct: float | None
    # Economia justa: só compara o mesmo produto/tamanho (mesmo grupo).
    comparable_worst: Product | None = None
    comparable_savings_pct: float | None = None


def build_adapters(
    chain_slugs: list[str] | tuple[str, ...] | None = None,
    include_reverse: bool = False,
) -> list[Adapter]:
    configs = list(config.TIER_A)
    if include_reverse and config.ENABLE_REVERSE_API:
        configs.extend(config.TIER_B)

    if chain_slugs:
        wanted = set(chain_slugs)
        configs = [chain for chain in configs if chain.slug in wanted]

    adapter_classes = {
        "vtex": VtexAdapter,
        "mateus": MateusAdapter,
        "vipcommerce": VipCommerceAdapter,
    }
    adapters: list[Adapter] = []
    for chain in configs:
        if not chain.implemented:
            continue
        adapter_class = adapter_classes.get(chain.platform)
        if adapter_class is None:
            logger.error(
                "Plataforma desconhecida para %s: %s", chain.slug, chain.platform
            )
            continue
        adapters.append(adapter_class(chain))
    return adapters


def _fetch_one(adapter: Adapter, term: str, max_pages: int | None) -> ChainResult:
    started = perf_counter()
    products: list[Product] = []
    error: str | None = None

    try:
        products = adapter.fetch(term, max_pages=max_pages)
    except HttpError as exc:
        error = exc.message
    except AdapterError as exc:
        error = str(exc)
    except Exception:
        logger.exception("Falha inesperada na rede %s", adapter.name)
        error = "resposta inesperada"
    finally:
        with contextlib.suppress(Exception):  # fechamento best effort
            adapter.close()

    elapsed_ms = int((perf_counter() - started) * 1000)
    logger.info(
        "busca rede=%s termo=%r status=%s itens=%d ms=%d",
        adapter.slug,
        term,
        f"erro:{error}" if error else "ok",
        len(products),
        elapsed_ms,
    )
    return ChainResult(
        chain=adapter.name,
        products=products,
        error=error,
        elapsed_ms=elapsed_ms,
    )


def search(
    term: str,
    chain_slugs: list[str] | tuple[str, ...] | None = None,
    include_reverse: bool = False,
    adapters: list[Adapter] | None = None,
    max_pages: int | None = None,
) -> list[ChainResult]:
    """Busca em paralelo. Uma falha não derruba as demais redes."""

    term = (term or "").strip()
    if not term:
        return []

    selected = (
        list(adapters)
        if adapters is not None
        else build_adapters(chain_slugs=chain_slugs, include_reverse=include_reverse)
    )
    if not selected:
        return []

    results: dict[str, ChainResult] = {}
    executor = ThreadPoolExecutor(
        max_workers=len(selected), thread_name_prefix="radar-preco-ne"
    )
    futures = {
        executor.submit(_fetch_one, adapter, term, max_pages): adapter
        for adapter in selected
    }
    timed_out = False

    try:
        for future in as_completed(futures, timeout=config.GLOBAL_TIMEOUT):
            adapter = futures[future]
            try:
                results[adapter.slug] = future.result()
            except Exception:
                logger.exception("Falha ao coletar resultado da rede %s", adapter.name)
                results[adapter.slug] = ChainResult(
                    chain=adapter.name, error="resposta inesperada"
                )
    except FuturesTimeoutError:
        timed_out = True
        for future, adapter in futures.items():
            if adapter.slug not in results:
                future.cancel()
                results[adapter.slug] = ChainResult(
                    chain=adapter.name, error="tempo esgotado"
                )
    finally:
        executor.shutdown(wait=not timed_out, cancel_futures=timed_out)

    ordered = [results[a.slug] for a in selected if a.slug in results]
    return backfill_package_sizes(ordered)


def backfill_package_sizes(results: list[ChainResult]) -> list[ChainResult]:
    """Completa tamanho ausente usando o mesmo EAN de outra rede.

    Ex.: "Budweiser Multipack 350ml" não diz a quantidade, mas o mesmo EAN
    aparece em outra rede como "350ml com 12 Unidades" -> 4,2 L.
    Nunca sobrescreve um tamanho já identificado.
    """

    known: dict[str, tuple[float, str]] = {}
    for result in results:
        for product in result.products:
            if (
                product.ean
                and product.package_size is not None
                and product.package_unit is not None
            ):
                known.setdefault(
                    product.ean, (product.package_size, product.package_unit)
                )

    if not known:
        return results

    for result in results:
        updated: list[Product] = []
        for product in result.products:
            if product.package_size is None and product.ean in known:
                size, unit = known[product.ean]
                product = replace(
                    product,
                    package_size=size,
                    package_unit=unit,
                    unit_price=compute_unit_price(product.price, size),
                )
            updated.append(product)
        result.products = updated

    return results


def sort_products(products: list[Product]) -> list[Product]:
    """Preço unitário asc; sem unidade vai para o fim, desempatado por preço."""

    return sorted(
        products,
        key=lambda p: (
            p.unit_price is None,
            p.unit_price if p.unit_price is not None else p.price,
            p.price,
        ),
    )


def rank(results: list[ChainResult]) -> Ranking:
    products = [product for result in results for product in result.products]

    best_by_chain: dict[str, Product] = {}
    for result in results:
        if result.products:
            best_by_chain[result.chain] = min(
                result.products,
                key=lambda p: (
                    p.unit_price is None,
                    p.unit_price if p.unit_price is not None else p.price,
                    p.price,
                ),
            )

    with_unit = [p for p in products if p.unit_price is not None]
    if not with_unit:
        return Ranking(best_by_chain, None, None, None)

    best_overall = min(with_unit, key=lambda p: (p.unit_price, p.price))
    worst_overall = max(with_unit, key=lambda p: (p.unit_price, p.price))
    savings_pct: float | None = None
    if best_overall.unit_price and worst_overall.unit_price:
        savings_pct = 1 - (best_overall.unit_price / worst_overall.unit_price)

    comparable_worst: Product | None = None
    comparable_savings: float | None = None
    best_group = next(
        (
            group
            for group in group_products(products)
            if any(product is best_overall for product in group.products)
        ),
        None,
    )
    if best_group is not None:
        group_prices = [
            product for product in best_group.products if product.unit_price is not None
        ]
        if len(group_prices) >= 2:
            comparable_worst = max(group_prices, key=lambda p: (p.unit_price, p.price))
            if best_overall.unit_price and comparable_worst.unit_price:
                comparable_savings = 1 - (
                    best_overall.unit_price / comparable_worst.unit_price
                )

    return Ranking(
        best_by_chain,
        best_overall,
        worst_overall,
        savings_pct,
        comparable_worst,
        comparable_savings,
    )
