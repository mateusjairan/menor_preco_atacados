"""Configuração central: redes, flags e limites do Radar de Preço NE."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """Carrega `.env` da raiz sem sobrescrever variáveis já definidas."""

    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.1) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


@dataclass(frozen=True)
class ChainConfig:
    """Metadados de uma rede. `base_url` é None para Tier B ainda não homologado."""

    name: str
    slug: str
    base_url: str | None
    access: str  # "public" | "reverse"
    region: str = ""


# --- Tier A: API pública VTEX (o produto) -----------------------------------
TIER_A: tuple[ChainConfig, ...] = (
    ChainConfig(
        "GBarbosa",
        "gbarbosa",
        "https://www.gbarbosa.com.br",
        "public",
        "BA, SE, AL, PE, CE",
    ),
    ChainConfig(
        "Mercantil Atacado",
        "mercantil",
        "https://www.mercantilatacado.com.br",
        "public",
        "BA",
    ),
    ChainConfig(
        "Hiperideal",
        "hiperideal",
        "https://www.hiperideal.com.br",
        "public",
        "BA",
    ),
    ChainConfig(
        "Atacadão",
        "atacadao",
        "https://www.atacadao.com.br",
        "public",
        "Nacional/NE",
    ),
    ChainConfig(
        "Atacadão Treichel",
        "treichel",
        "https://delivery.atacadotreichel.com.br",
        "public",
        "CE",
    ),
)

# --- Tier B: API reversa (experimental, desligada por padrão) ----------------
TIER_B: tuple[ChainConfig, ...] = (
    ChainConfig("Pinheiro (Bom Vizinho)", "pinheiro", None, "reverse", "CE"),
    ChainConfig("Nordestão", "nordestao", None, "reverse", "RN"),
    ChainConfig("Diniz", "diniz", None, "reverse", "CE"),
)

CHAINS: tuple[ChainConfig, ...] = TIER_A + TIER_B
CHAINS_BY_SLUG: dict[str, ChainConfig] = {chain.slug: chain for chain in CHAINS}

# --- Flags e limites ---------------------------------------------------------
ENABLE_REVERSE_API: bool = _env_bool("ENABLE_REVERSE_API", False)
HTTP_TIMEOUT: float = _env_float("HTTP_TIMEOUT", 10.0)
MAX_PAGES: int = _env_int("MAX_PAGES", 2)
IMPERSONATE: str = os.getenv("IMPERSONATE", "chrome").strip() or "chrome"
CONTACT_EMAIL: str = os.getenv("CONTACT_EMAIL", "contato@seudominio.com.br").strip()

USER_AGENT = f"RadarPrecoNE/0.1 (+{CONTACT_EMAIL})"
IMPERSONATE_FALLBACKS: tuple[str, ...] = ("chrome110", "safari17_0")

PAGE_SIZE = 50
RATE_LIMIT_PER_SECOND = 2.0
GLOBAL_TIMEOUT = 20.0
CACHE_TTL = 300
