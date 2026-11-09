"""Adapter VTEX (Tier A) — API pública de catálogo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .. import config
from ..http import HttpClient, HttpError
from ..models import Product
from ..units import compute_unit_price, parse_package
from .base import Adapter, AdapterError

logger = logging.getLogger(__name__)

SEARCH_PATH = "/api/catalog_system/pub/products/search"


class VtexAdapter(Adapter):
    def __init__(
        self,
        chain,
        client: HttpClient | None = None,
        page_size: int = config.PAGE_SIZE,
    ) -> None:
        super().__init__(chain)
        self.client = client or HttpClient(chain.slug)
        self.page_size = page_size

    def fetch(self, term: str, max_pages: int | None = None) -> list[Product]:
        term = (term or "").strip()
        if not term:
            return []
        if not self.chain.base_url:
            raise AdapterError("rede sem catálogo configurado")

        pages = max(1, max_pages or config.MAX_PAGES)
        products: list[Product] = []

        for page in range(pages):
            start = page * self.page_size
            try:
                payload = self.client.get_json(
                    f"{self.chain.base_url}{SEARCH_PATH}",
                    {
                        "ft": term,
                        "_from": start,
                        "_to": start + self.page_size - 1,
                    },
                )
            except HttpError:
                raise
            except Exception as exc:  # pragma: no cover - defesa contra payload exótico
                raise AdapterError("resposta inesperada") from exc

            if not isinstance(payload, list):
                raise AdapterError("resposta inesperada")
            if not payload:
                break

            for raw in payload:
                if isinstance(raw, dict):
                    products.extend(self._parse_product(raw))

            if len(payload) < self.page_size:
                break

        return products

    def _parse_product(self, raw: dict[str, Any]) -> list[Product]:
        name_fallback = str(raw.get("productName") or "").strip()
        brand = str(raw.get("brand") or "").strip() or None
        link_text = str(raw.get("linkText") or "").strip()
        link = str(raw.get("link") or "").strip()
        if not link and link_text and self.chain.base_url:
            link = f"{self.chain.base_url}/{link_text}/p"

        collected_at = datetime.now(UTC)
        products: list[Product] = []

        for item in raw.get("items") or []:
            if not isinstance(item, dict):
                continue

            offer = _best_offer(item.get("sellers") or [])
            if offer is None:
                continue

            name = str(item.get("name") or name_fallback).strip()
            if not name:
                continue

            price = _as_positive_float(offer.get("Price"))
            if price is None:
                continue

            list_price = _as_positive_float(offer.get("ListPrice"))
            package_size, package_unit = parse_package(name)
            unit_price = compute_unit_price(price, package_size)

            products.append(
                Product(
                    chain=self.chain.name,
                    chain_slug=self.chain.slug,
                    name=name,
                    brand=brand,
                    ean=_clean_ean(item.get("ean")),
                    price=price,
                    list_price=list_price,
                    package_size=package_size,
                    package_unit=package_unit,
                    unit_price=unit_price,
                    url=link or (self.chain.base_url or ""),
                    image_url=_first_image(item.get("images") or []),
                    collected_at=collected_at,
                    access=self.chain.access,
                )
            )

        return products

    def close(self) -> None:
        self.client.close()


def _as_positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clean_ean(value: Any) -> str | None:
    if value is None:
        return None
    ean = str(value).strip()
    if not ean or not ean.isdigit() or set(ean) == {"0"}:
        return None
    return ean


def _best_offer(sellers: list[Any]) -> dict[str, Any] | None:
    """Menor preço entre sellers com estoque disponível."""

    best: tuple[float, dict[str, Any]] | None = None
    for seller in sellers:
        if not isinstance(seller, dict):
            continue
        offer = seller.get("commertialOffer")
        if not isinstance(offer, dict):
            continue
        available = _as_positive_float(offer.get("AvailableQuantity"))
        if available is None:
            continue
        price = _as_positive_float(offer.get("Price"))
        if price is None:
            continue
        if best is None or price < best[0]:
            best = (price, offer)
    return best[1] if best else None


def _first_image(images: list[Any]) -> str | None:
    for image in images:
        if isinstance(image, dict):
            url = str(image.get("imageUrl") or "").strip()
            if url:
                return url
    return None
