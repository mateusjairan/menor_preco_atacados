"""Adapter VipCommerce (Tier B) — catálogo anônimo de lojas white-label.

O fluxo é o mesmo do front-end público: resolve organização/filial pelo domínio,
faz login anônimo da loja e consulta a busca. A chave de loja é pública no bundle
da plataforma, mas não é versionada: configure `VIPCOMMERCE_LOJA_KEY`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from .. import config
from ..http import HttpClient, HttpError
from ..models import Product
from ..units import compute_unit_price, parse_package
from .base import Adapter, AdapterError

BASE_URL = "https://services.vipcommerce.com.br/api-admin/v1"
IMAGE_BASE = (
    "https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/250x250/"
)
FILIAL_ID = 1
CENTRO_ID = 1


class VipCommerceAdapter(Adapter):
    def __init__(
        self,
        chain,
        client: HttpClient | None = None,
        page_size: int = 20,
    ) -> None:
        super().__init__(chain)
        self.client = client or HttpClient(chain.slug)
        self.page_size = page_size
        self._organization_id: int | None = None
        self._host: str | None = None
        self._logged = False

    def fetch(self, term: str, max_pages: int | None = None) -> list[Product]:
        term = (term or "").strip()
        if not term:
            return []

        organization_id, host = self._resolve_context()
        self._login(organization_id, host)

        pages = max(1, max_pages or config.MAX_PAGES)
        products: list[Product] = []

        for page in range(1, pages + 1):
            path = (
                f"/org/{organization_id}/filial/{FILIAL_ID}/"
                f"centro_distribuicao/{CENTRO_ID}/loja/buscas/produtos/termo/"
                f"{quote(term, safe='')}"
            )
            try:
                payload = self.client.get_json(f"{BASE_URL}{path}", {"page": page})
            except HttpError:
                raise
            if not isinstance(payload, dict):
                raise AdapterError("resposta inesperada")

            data = payload.get("data")
            if not isinstance(data, dict) or "produtos" not in data:
                raise AdapterError("resposta inesperada")
            items = data.get("produtos") or []
            if not isinstance(items, list):
                raise AdapterError("resposta inesperada")
            if not items:
                break

            for item in items:
                if isinstance(item, dict):
                    product = self._parse_product(item)
                    if product is not None:
                        products.append(product)

            paginator = payload.get("paginator") or {}
            total_pages = _positive_int(paginator.get("total_pages"))
            if total_pages is not None and page >= total_pages:
                break
            if len(items) < self.page_size:
                break

        return products

    def _resolve_context(self) -> tuple[int, str]:
        if self._organization_id is not None and self._host is not None:
            return self._organization_id, self._host
        if not self.chain.base_url:
            raise AdapterError("rede sem catálogo configurado")

        host = (urlparse(self.chain.base_url).hostname or "").removeprefix("www.")
        payload = self.client.get_json(
            f"{BASE_URL}/organizacoes/filiais/dominio/{quote(host)}"
        )
        if not isinstance(payload, dict):
            raise AdapterError("resposta inesperada")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise AdapterError("resposta inesperada")
        organization = data.get("organizacao") or {}
        organization_id = _positive_int(organization.get("id"))
        if organization_id is None:
            raise AdapterError("organização não encontrada para o domínio")

        self._organization_id = organization_id
        self._host = host
        self.client.headers.update(
            {
                "OrganizationId": str(organization_id),
                "DomainKey": host,
            }
        )
        return organization_id, host

    def _login(self, organization_id: int, host: str) -> None:
        if self._logged:
            return
        key = config.VIPCOMMERCE_LOJA_KEY
        if not key:
            raise AdapterError(
                "VIPCOMMERCE_LOJA_KEY não configurada; consulte docs/api/vipcommerce.md"
            )

        payload = self.client.post_json(
            f"{BASE_URL}/org/{organization_id}/auth/loja/login",
            {"domain": host, "username": "loja", "key": key},
        )
        if not isinstance(payload, dict):
            raise AdapterError("resposta inesperada")
        token = payload.get("data")
        if not isinstance(token, str) or not token:
            raise AdapterError("login da loja não retornou token")

        self.client.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "sessao-id": uuid.uuid4().hex,
            }
        )
        self._logged = True

    def _parse_product(self, item: dict) -> Product | None:
        if item.get("disponivel") is False:
            return None
        name = str(item.get("descricao") or "").strip()
        price = _positive_float(item.get("preco"))
        if not name or price is None:
            return None

        list_price = _positive_float(item.get("preco_original"))
        if list_price is not None and list_price <= price:
            list_price = None

        package_size, package_unit = parse_package(name)
        object_id = item.get("produto_id")
        link = str(item.get("link") or "").strip()
        base_url = (self.chain.base_url or "").rstrip("/")
        url = (
            f"{base_url}/produto/{object_id}/{link}"
            if object_id and link
            else f"{base_url}/"
        )
        image = str(item.get("imagem") or "").strip()
        brand = str(item.get("marca") or "").strip() or None

        return Product(
            chain=self.chain.name,
            chain_slug=self.chain.slug,
            name=name,
            brand=brand,
            ean=_clean_ean(item.get("codigo_barras")),
            price=price,
            list_price=list_price,
            package_size=package_size,
            package_unit=package_unit,
            unit_price=compute_unit_price(price, package_size),
            url=url,
            image_url=f"{IMAGE_BASE}{image}" if image else None,
            collected_at=datetime.now(UTC),
            access=self.chain.access,
        )

    def close(self) -> None:
        self.client.close()


def _positive_float(value) -> float | None:
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clean_ean(value) -> str | None:
    if value is None:
        return None
    ean = str(value).strip()
    if not ean or not ean.isdigit() or set(ean) == {"0"}:
        return None
    return ean
