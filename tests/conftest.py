from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.models import Product
from src.units import compute_unit_price


@pytest.fixture
def make_product():
    def factory(
        chain: str = "GBarbosa",
        chain_slug: str = "gbarbosa",
        name: str = "Leite Integral 1l",
        brand: str | None = "Marca",
        ean: str | None = None,
        price: float = 5.0,
        list_price: float | None = None,
        package_size: float | None = 1.0,
        package_unit: str | None = "l",
        unit_price: float | None = None,
        url: str | None = None,
        image_url: str | None = None,
        access: str = "public",
    ) -> Product:
        return Product(
            chain=chain,
            chain_slug=chain_slug,
            name=name,
            brand=brand,
            ean=ean,
            price=price,
            list_price=list_price,
            package_size=package_size,
            package_unit=package_unit,
            unit_price=(
                compute_unit_price(price, package_size)
                if unit_price is None
                else unit_price
            ),
            url=url or f"https://{chain_slug}.example/{name.replace(' ', '-')}",
            image_url=image_url,
            collected_at=datetime(2026, 1, 1, tzinfo=UTC),
            access=access,
        )

    return factory
