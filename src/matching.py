"""Matching cross-chain por EAN exato + fallback fuzzy, sem cruzar tamanhos."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .models import Product
from .units import strip_size

GROUP_THRESHOLD = 85.0
SIMILAR_THRESHOLD = 60.0

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SPACES_RE = re.compile(r"\s+")


def normalize_name(text: str | None) -> str:
    """Minúsculas, sem acento, pontuação trocada por espaço."""

    decomposed = unicodedata.normalize("NFKD", text or "")
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    lowered = without_accents.lower()
    return _SPACES_RE.sub(" ", _NON_ALNUM_RE.sub(" ", lowered)).strip()


def name_without_size(text: str | None) -> str:
    return normalize_name(strip_size(text or ""))


def _size_key(product: Product) -> tuple[str | None, float | None]:
    if product.package_unit is None or product.package_size is None:
        return None, None
    return product.package_unit, round(product.package_size, 6)


def _same_size(left: Product, right: Product) -> bool:
    left_key = _size_key(left)
    right_key = _size_key(right)
    if left_key == (None, None) and right_key == (None, None):
        return True
    if left_key == (None, None) or right_key == (None, None):
        return False
    return left_key == right_key


def match_score(left: Product, right: Product) -> float:
    """100 para EAN igual; 0 para EAN diferente/tamanho incompatível."""

    if left.ean and right.ean:
        return 100.0 if left.ean == right.ean else 0.0
    if not _same_size(left, right):
        return 0.0

    left_name = name_without_size(left.name)
    right_name = name_without_size(right.name)
    if not left_name or not right_name:
        return 0.0
    return float(fuzz.token_set_ratio(left_name, right_name))


@dataclass
class ProductGroup:
    key: str
    products: list[Product] = field(default_factory=list)
    score: float = 100.0
    similar: bool = False

    @property
    def display_name(self) -> str:
        return self.products[0].name if self.products else ""


def group_products(products: list[Product]) -> list[ProductGroup]:
    """Agrupa por EAN e, para itens sem EAN, por nome + mesmo tamanho/unidade."""

    groups: list[ProductGroup] = []
    ean_index: dict[str, ProductGroup] = {}
    buckets: dict[tuple[str | None, float | None], list[ProductGroup]] = {}

    for product in products:
        if not product.ean:
            continue
        key = f"ean:{product.ean}"
        group = ean_index.get(key)
        if group is None:
            group = ProductGroup(key=key, products=[product], score=100.0)
            ean_index[key] = group
            groups.append(group)
            buckets.setdefault(_size_key(product), []).append(group)
        else:
            group.products.append(product)

    for product in products:
        if product.ean:
            continue

        bucket = buckets.get(_size_key(product), [])
        best_score = -1.0
        best_group: ProductGroup | None = None
        for group in bucket:
            score = match_score(product, group.products[0])
            if score > best_score:
                best_score = score
                best_group = group

        if best_group is not None and best_score >= SIMILAR_THRESHOLD:
            best_group.products.append(product)
            if best_score < GROUP_THRESHOLD:
                best_group.similar = True
            best_group.score = min(best_group.score, best_score)
            continue

        unit, size = _size_key(product)
        group = ProductGroup(
            key=f"name:{name_without_size(product.name)}|{unit}|{size}",
            products=[product],
            score=100.0,
        )
        groups.append(group)
        buckets.setdefault(_size_key(product), []).append(group)

    return groups


def best_in_group(group: ProductGroup) -> Product | None:
    """Menor preço unitário; se o grupo não tem unidade, cai para preço."""

    if not group.products:
        return None
    with_unit = [p for p in group.products if p.unit_price is not None]
    pool = with_unit or group.products
    return min(pool, key=lambda p: (p.unit_price or 0.0, p.price))


def similar_group_count(groups: list[ProductGroup]) -> int:
    return sum(1 for group in groups if group.similar and len(group.products) > 1)
