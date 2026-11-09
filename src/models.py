"""Modelo de dados do Radar de Preço NE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Product:
    chain: str
    chain_slug: str
    name: str
    brand: str | None
    ean: str | None
    price: float  # BRL
    list_price: float | None
    package_size: float | None  # em unidade base (kg, l, un)
    package_unit: str | None  # "kg" | "l" | "un"
    unit_price: float | None  # R$ por kg/l/un
    url: str
    image_url: str | None
    collected_at: datetime
    access: str  # "public" | "reverse"


@dataclass
class ChainResult:
    chain: str
    products: list[Product] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None
