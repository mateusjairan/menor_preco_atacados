"""Adapter do Grupo Mateus (Mateus Mais) — API anônima do catálogo.

O endpoint é o mesmo usado pelo SPA público da rede. Ele não é documentado,
portanto a fonte fica no Tier B (feature flag) e não deve ser ligada sem revisão
de ToS. A praça padrão é São Luís/MA; pode ser trocada por ambiente.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from .. import config
from ..http import HttpClient, HttpError
from ..models import Product
from ..units import compute_unit_price, parse_package
from .base import Adapter, AdapterError

BASE_URL = "https://app.mateusmais.com.br"
SEARCH_PATH = "/api/products/internal/v1/service/priority"
MARKETS_PATH = "/api/products/market-category-group/"
INDEX = "SHOWCASE_catalog_product_api_index_PROD_total_quantity_sold_desc"
SERVICE = "meilisearch"


class MateusAdapter(Adapter):
    def __init__(
        self,
        chain,
        client: HttpClient | None = None,
        market_id: str | None = None,
        page_size: int = config.PAGE_SIZE,
    ) -> None:
        super().__init__(chain)
        self.client = client or HttpClient(chain.slug)
        self.market_id = market_id or config.MATEUS_MARKET_ID
        self.page_size = page_size

    def fetch(self, term: str, max_pages: int | None = None) -> list[Product]:
        term = (term or "").strip()
        if not term:
            return []

        market_id = self._resolve_market_id()
        pages = max(1, max_pages or config.MAX_PAGES)
        products: list[Product] = []

        for page in range(pages):
            params = urlencode(
                {
                    "page": page,
                    "hitsPerPage": self.page_size,
                    "query": term,
                    "facetFilters": json.dumps(
                        [[f"market_id:{market_id}"], ["for_sale:true"]]
                    ),
                }
            )
            body = {
                "facets": ["specification.*", "brand", "nodes"],
                "params": params,
                "index": INDEX,
                "service": SERVICE,
                "market_priority": {"market_ids": [market_id]},
            }
            payload = self.client.post_json(f"{BASE_URL}{SEARCH_PATH}", body)
            if not isinstance(payload, dict) or "hits" not in payload:
                raise AdapterError("resposta inesperada")
            hits = payload.get("hits") or []
            if not isinstance(hits, list):
                raise AdapterError("resposta inesperada")
            if not hits:
                break

            for hit in hits:
                if isinstance(hit, dict):
                    product = self._parse_hit(hit, market_id)
                    if product is not None:
                        products.append(product)

            nb_pages = _positive_int(payload.get("nbPages"))
            if nb_pages is not None and page + 1 >= nb_pages:
                break
            if len(hits) < self.page_size:
                break

        return products

    def _resolve_market_id(self) -> str:
        if self.market_id:
            return self.market_id

        try:
            payload = self.client.get_json(
                f"{BASE_URL}{MARKETS_PATH}",
                {
                    "latitude": config.MATEUS_LATITUDE,
                    "longitude": config.MATEUS_LONGITUDE,
                    "city_code": config.MATEUS_CITY_CODE,
                },
            )
        except HttpError as exc:
            raise AdapterError(
                f"não foi possível resolver a loja Mateus: {exc.message}"
            ) from exc

        if isinstance(payload, list):
            for group in payload:
                if not isinstance(group, dict):
                    continue
                if str(group.get("name") or "").casefold() != "mercado":
                    continue
                for market in group.get("markets") or []:
                    if not isinstance(market, dict):
                        continue
                    if market.get("online_sell") and market.get("id"):
                        self.market_id = str(market["id"])
                        return self.market_id

        raise AdapterError(
            "loja do Grupo Mateus não encontrada para a praça configurada"
        )

    def _parse_hit(self, hit: dict, market_id: str) -> Product | None:
        if not hit.get("for_sale", True) or hit.get("is_active") is False:
            return None

        name = str(hit.get("name") or "").strip()
        price = _positive_float(hit.get("sale_price")) or _positive_float(
            hit.get("price")
        )
        if not name or price is None:
            return None

        stock = _finite_float(hit.get("amount_in_stock"))
        if stock is not None and stock <= 0:
            return None

        list_price = _positive_float(hit.get("price"))
        if list_price is not None and list_price <= price:
            list_price = None

        package_size, package_unit = _measure_package(
            hit.get("measure"), hit.get("measure_type")
        )
        if package_size is None:
            package_size, package_unit = parse_package(name)

        object_id = hit.get("objectID") or hit.get("id")
        url = (
            f"https://www.mateusmais.com.br/produtos/{market_id}/{object_id}"
            if object_id
            else "https://www.mateusmais.com.br/"
        )
        brand = str(hit.get("brand") or "").strip() or None

        return Product(
            chain=self.chain.name,
            chain_slug=self.chain.slug,
            name=name,
            brand=brand,
            ean=_clean_ean(hit.get("barcode")),
            price=price,
            list_price=list_price,
            package_size=package_size,
            package_unit=package_unit,
            unit_price=compute_unit_price(price, package_size),
            url=url,
            image_url=hit.get("image") or hit.get("small_image"),
            collected_at=datetime.now(UTC),
            access=self.chain.access,
        )

    def close(self) -> None:
        self.client.close()


def _finite_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value) -> float | None:
    number = _finite_float(value)
    return number if number is not None and number > 0 else None


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _measure_package(measure, measure_type) -> tuple[float | None, str | None]:
    value = _positive_float(measure)
    if value is None or not measure_type:
        return None, None

    unit = str(measure_type).strip().casefold()
    if unit in {"g", "grama", "gramas"}:
        return value * 0.001, "kg"
    if unit in {"kg", "quilograma", "quilogramas"}:
        return value, "kg"
    if unit in {"ml", "mililitro", "mililitros"}:
        return value * 0.001, "l"
    if unit in {"l", "lt", "litro", "litros"}:
        return value, "l"
    if unit in {"un", "unid", "unidade", "unidades"}:
        return value, "un"
    return None, None


def _clean_ean(value) -> str | None:
    if value is None:
        return None
    ean = str(value).strip()
    if not ean or not ean.isdigit() or set(ean) == {"0"}:
        return None
    return ean
