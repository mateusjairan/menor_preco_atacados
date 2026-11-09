"""Contrato comum dos adapters de rede."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import ChainConfig
from ..models import Product


class AdapterError(RuntimeError):
    """Falha esperada de um adapter, com mensagem adequada à UI."""


class Adapter(ABC):
    def __init__(self, chain: ChainConfig) -> None:
        self.chain = chain

    @property
    def slug(self) -> str:
        return self.chain.slug

    @property
    def name(self) -> str:
        return self.chain.name

    @abstractmethod
    def fetch(self, term: str, max_pages: int | None = None) -> list[Product]:
        """Busca o termo e devolve produtos normalizados."""

    def close(self) -> None:
        """Libera recursos de rede, se houver."""
        return None
