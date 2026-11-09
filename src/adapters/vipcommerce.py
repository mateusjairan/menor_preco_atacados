"""Adapter VipCommerce (Tier B) — placeholder até homologação.

O fluxo foi identificado (login anônimo da loja, resolução de filial por
domínio e catálogo em `/org/{orgId}/...`), mas os contratos de resposta e os
ToS ainda precisam ser validados. Ver `docs/api/vipcommerce.md`.

Regra do projeto: não inventar campo nem ligar rede não homologada por padrão.
"""

from __future__ import annotations

from ..models import Product
from .base import Adapter, AdapterError


class VipCommerceAdapter(Adapter):
    def fetch(self, term: str, max_pages: int | None = None) -> list[Product]:
        raise AdapterError(
            "API reversa não homologada (Tier B); consulte docs/api/vipcommerce.md"
        )
