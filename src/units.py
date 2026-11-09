"""Parse de tamanho de embalagem e cálculo de preço unitário.

O tamanho considerado é o **conteúdo total** da embalagem. Exemplos:

- `Coca-Cola 2L` -> 2 L
- `Coca-Cola 6 x 350ml` -> 2,1 L
- `Pack c/ 6 Unid de 350ml` -> 2,1 L
- `Kit Coca-Cola 2L + Fanta 2L` -> 4 L
"""

from __future__ import annotations

import re

_UNIT_TOKEN = (
    r"kg|quilogramas?|quilos?|g|gramas?|gr|mg|mll|ml|mililitros?|l|litros?|lts?"
    r"|un|unid(?:ade)?s?|pct|pacote|caps"
)
_CONTENT_UNIT_TOKEN = (
    r"(?:kg|quilogramas?|quilos?|g|gramas?|gr|mg|mll|ml|mililitros?|l|litros?|lts?)"
)
_COUNT_NOUN = (
    r"(?:unidades?|unid(?:ade)?s?|un|garrafas?|latas?|caixas?|pacotes?|fardos?"
    r"|rolos?|pct)"
)

# `6x350ml`, `2 x 2L`, `12×1 L`, `6*350ml`.
_MULTIPLIER_RE = re.compile(
    rf"(?<![\w])(\d+)\s*[xX×*]\s*(\d+(?:[.,]\d+)?)\s*({_UNIT_TOKEN})\b",
    re.IGNORECASE,
)

# Tamanho isolado: `1kg`, `500g`, `900ml`, `1,5l`, `30un`, `1 litro`.
_SIZE_RE = re.compile(
    rf"(?<![\w])(\d+(?:[.,]\d+)?)\s*({_UNIT_TOKEN})\b",
    re.IGNORECASE,
)

# `Pack 6`, `Pack c/ 6`, `Pack C6`. O lookahead evita ler `Pack 2L` como 2 un.
_PACK_RE = re.compile(
    rf"(?<![\w])pack\s*(?:c\s*/?\s*|com\s+|de\s+)?(\d+)(?!\d)"
    rf"(?!\s*{_CONTENT_UNIT_TOKEN}\b)",
    re.IGNORECASE,
)

# `6-pack`, `12 pack`.
_N_PACK_RE = re.compile(
    rf"(?<![\w])(\d+)(?!\d)\s*[- ]?\s*pack\b" rf"(?!\s*{_CONTENT_UNIT_TOKEN}\b)",
    re.IGNORECASE,
)

# "Multipack 350ml", "Pack 2L", "Fardo 350ml": sem quantidade explícita,
# o total é desconhecido. Melhor ficar sem preço unitário do que chutar.
# "Stand Pack" é formato de embalagem, não multiplicador.
_AMBIGUOUS_PACK_RE = re.compile(r"\b(?:multipack|pack|fardo)\b", re.IGNORECASE)
_STAND_PACK_RE = re.compile(r"stand\s*pack", re.IGNORECASE)

# `6 unidades`, `6 latas`, `12un`.
_COUNT_NOUN_RE = re.compile(
    rf"(?<![\w])(\d+)(?!\d)\s*{_COUNT_NOUN}\b",
    re.IGNORECASE,
)

# `fardo 12`, `caixa com 6`, `pacote de 12`.
_CONTAINER_RE = re.compile(
    rf"(?<![\w])(?:fardo|caixa|pacote)\s*"
    rf"(?:com\s+|c\s*/?\s*|de\s+)?(\d+)(?!\d)"
    rf"(?!\s*{_CONTENT_UNIT_TOKEN}\b)",
    re.IGNORECASE,
)

# `leve 6 pague 5`, `leve3pague 2` e `leve 6`.
# O lookahead evita ler `Leve 1l`/`Leve 500ml` como contagem.
_LEVE_PAGUE_RE = re.compile(
    rf"(?<![\w])(?:leve|lv)\s*(\d+)(?!\d)(?!\s*{_CONTENT_UNIT_TOKEN}\b)"
    rf"\s*(?:pague|pg)\s*\d+",
    re.IGNORECASE,
)
_LEVE_RE = re.compile(
    rf"(?<![\w])(?:leve|lv)\s*(\d+)(?!\d)(?!\s*{_CONTENT_UNIT_TOKEN}\b)",
    re.IGNORECASE,
)

# `Leve 500 Pague 350ml`: o volume/unidade após "pague" define o tamanho.
_LEVE_PAGUE_SIZE_RE = re.compile(
    rf"(?<![\w])(?:leve|lv)\s*(\d+)\s*(?:pague|pg)\s*"
    rf"(\d+(?:[.,]\d+)?)\s*({_CONTENT_UNIT_TOKEN})\b",
    re.IGNORECASE,
)

# `c/6` e `c6`.
_C_SLASH_RE = re.compile(r"(?<![\w])c\s*/\s*(\d+)\b", re.IGNORECASE)
_C_NUM_RE = re.compile(r"(?<![\w])c(\d+)\b", re.IGNORECASE)

_COUNT_PATTERNS = (
    _PACK_RE,
    _N_PACK_RE,
    _LEVE_PAGUE_RE,
    _LEVE_RE,
    _CONTAINER_RE,
    _COUNT_NOUN_RE,
    _C_SLASH_RE,
    _C_NUM_RE,
)

_MASS_UNITS = {
    "kg": ("kg", 1.0),
    "quilo": ("kg", 1.0),
    "quilos": ("kg", 1.0),
    "quilograma": ("kg", 1.0),
    "quilogramas": ("kg", 1.0),
    "g": ("kg", 0.001),
    "grama": ("kg", 0.001),
    "gramas": ("kg", 0.001),
    "gr": ("kg", 0.001),
    "mg": ("kg", 0.000001),
}

_VOLUME_UNITS = {
    "l": ("l", 1.0),
    "litro": ("l", 1.0),
    "litros": ("l", 1.0),
    "lt": ("l", 1.0),
    "lts": ("l", 1.0),
    "ml": ("l", 0.001),
    "mll": ("l", 0.001),
    "mililitro": ("l", 0.001),
    "mililitros": ("l", 0.001),
}

_COUNT_UNITS = {
    "un": "un",
    "unid": "un",
    "unidade": "un",
    "unidades": "un",
    "pct": "un",
    "pacote": "un",
    "caps": "un",
}


_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
_LETTER_DIGIT_RE = re.compile(r"(?<=[A-Za-z])(?=\d)")
_DIGIT_LETTER_RE = re.compile(r"(?<=\d)(?=[A-Za-z])")
_NUMBER_COMMA_RE = re.compile(r"(?<=\d)\s+([.,])\s*(?=\d)")
_L_P_SHORTHAND_RE = re.compile(
    rf"(?<![\w])l\s+(\d+)\s+p\s+(\d+(?:[.,]\d+)?)\s+({_CONTENT_UNIT_TOKEN})\b",
    re.IGNORECASE,
)


def _prepare(text: str) -> str:
    """Separa tamanho grudado em palavra: `Vidro250ml`, `360mlOferta`, `1 ,15Kg`."""

    prepared = _CAMEL_RE.sub(" ", text)
    prepared = _LETTER_DIGIT_RE.sub(" ", prepared)
    prepared = _DIGIT_LETTER_RE.sub(" ", prepared)
    prepared = _NUMBER_COMMA_RE.sub(r"\1", prepared)
    prepared = re.sub(r"\s+", " ", prepared).strip()

    # `L500P350ml`/`L 500 P 350 ml` é a forma curta de Leve/Pague.
    return _L_P_SHORTHAND_RE.sub(
        lambda match: (
            f"Leve {match.group(1)} Pague {match.group(2)} {match.group(3)}"
        ),
        prepared,
    )


def _to_float(raw: str) -> float | None:
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    return value if value > 0 else None


def _normalize_unit(raw: str) -> tuple[str, float] | None:
    token = raw.strip().lower()
    if token in _MASS_UNITS:
        return _MASS_UNITS[token]
    if token in _VOLUME_UNITS:
        return _VOLUME_UNITS[token]
    if token in _COUNT_UNITS:
        return (_COUNT_UNITS[token], 1.0)
    return None


def _combine(components: list[tuple[float, str]]) -> tuple[float | None, str | None]:
    if not components:
        return None, None
    units = {unit for _, unit in components}
    if len(units) != 1:
        return None, None
    return sum(value for value, _ in components), units.pop()


def _extract_count(text: str) -> tuple[int, int, int] | None:
    """Retorna (quantidade, início, fim) do primeiro indício de multipack."""

    for pattern in _COUNT_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            count = _to_float(match.group(1))
            if count is not None and count.is_integer():
                return int(count), match.start(), match.end()
    return None


def _content_sizes(text: str) -> list[tuple[float, str, int, int]]:
    sizes: list[tuple[float, str, int, int]] = []
    for match in _SIZE_RE.finditer(text):
        value = _to_float(match.group(1))
        normalized = _normalize_unit(match.group(2))
        if value is None or normalized is None:
            continue
        unit, factor = normalized
        if unit in {"kg", "l"}:
            sizes.append((value * factor, unit, match.start(), match.end()))
    return sizes


def _has_kit_separator(text: str) -> bool:
    lowered = text.lower()
    return (
        "+" in text
        or "kit" in lowered
        or re.search(r"(?<=\s)e(?=\s)", lowered) is not None
    )


def _is_ambiguous_pack(text: str) -> bool:
    if _STAND_PACK_RE.search(text):
        return False
    return _AMBIGUOUS_PACK_RE.search(text) is not None


def parse_package(text: str | None) -> tuple[float | None, str | None]:
    """Extrai o conteúdo total e a unidade base de um nome/descrição."""

    if not text:
        return None, None

    text = _prepare(text)
    components: list[tuple[float, str]] = []
    working = text

    # 1) Multiplicadores explícitos: 6x350ml, 2x2L, 12 x 1 L.
    for match in _MULTIPLIER_RE.finditer(text):
        count = _to_float(match.group(1))
        value = _to_float(match.group(2))
        normalized = _normalize_unit(match.group(3))
        if count is None or value is None or normalized is None:
            continue
        unit, factor = normalized
        components.append((count * value * factor, unit))
        working = (
            working[: match.start()]
            + " " * (match.end() - match.start())
            + working[match.end() :]
        )

    lowered = text.lower()
    is_paper = "papel higi" in lowered or "papel toalha" in lowered

    # 2) Oferta "Leve 500 Pague 350ml": entrega 500 ml, sem contar 500 un.
    # Papel não entra aqui: o peso é do produto, não volume multiplicável.
    leve_size_matched = False
    if not is_paper:
        for match in _LEVE_PAGUE_SIZE_RE.finditer(text):
            first = _to_float(match.group(1))
            second = _to_float(match.group(2))
            normalized = _normalize_unit(match.group(3))
            if first is None or second is None or normalized is None:
                continue
            # Em "Leve X Pague Y", X deve ser maior que Y. Evita lixo como
            # "Leve 16 Pague 1596g" (nome concatenado).
            if first <= second:
                continue
            unit, factor = normalized
            components.append((first * factor, unit))
            working = (
                working[: match.start()]
                + " " * (match.end() - match.start())
                + working[match.end() :]
            )
            leve_size_matched = True

    # 3) Tamanhos isolados (já sem os trechos de multiplicador/oferta).
    content = _content_sizes(working)
    count_match = None if leve_size_matched else _extract_count(text)
    used: set[int] = set()

    if count_match is not None:
        count, count_start, count_end = count_match
        # Nome malformado tipo "Pague 1596g": o tamanho se sobrepõe à contagem.
        content = [
            size
            for size in content
            if not (size[2] < count_end and size[3] > count_start)
        ]

        # Papel higiênico/toalha é vendido por rolo. O peso em gramas é do
        # produto, não conteúdo multiplicável; preço/unidade é o justo.
        has_roll = "rolo" in text[count_start:count_end].lower()
        if is_paper or has_roll:
            return float(count), "un"

    # 4) "6 unidades de 350ml": associa a contagem ao tamanho mais próximo.
    if not components and count_match is not None and content:
        count, count_start, count_end = count_match
        after = [i for i, size in enumerate(content) if size[2] >= count_end]
        before = [i for i, size in enumerate(content) if size[3] <= count_start]
        chosen = after[0] if after else (before[-1] if before else None)
        if chosen is not None:
            value, unit, _, _ = content[chosen]
            components.append((count * value, unit))
            used.add(chosen)

    # 4) Pack/fardo sem quantidade: não dá para saber o conteúdo total.
    if (
        not components
        and content
        and not _has_kit_separator(text)
        and _is_ambiguous_pack(text)
    ):
        return None, None

    # 5) Kit com mais de um item: soma os conteúdos do mesmo tipo.
    extra = [size for i, size in enumerate(content) if i not in used]
    if components and extra and _has_kit_separator(text):
        components.extend((value, unit) for value, unit, _, _ in extra)
    elif not components:
        if len(content) > 1 and _has_kit_separator(text):
            components = [(value, unit) for value, unit, _, _ in content]
        elif content:
            value, unit, _, _ = content[0]
            components = [(value, unit)]

    combined = _combine(components)
    if combined[0] is not None:
        return combined

    # 5) Sem volume/massa: `6 unidades` ou `30un` são a própria embalagem.
    if count_match is not None:
        count, _, _ = count_match
        return float(count), "un"

    if content:
        value, unit, _, _ = content[0]
        return value, unit

    return None, None


def compute_unit_price(price: float | None, package_size: float | None) -> float | None:
    """Preço por kg/l/un. Sem tamanho confiável, não há ranking justo."""

    if price is None or package_size is None or package_size <= 0:
        return None
    return price / package_size


def strip_size(text: str) -> str:
    """Remove tamanhos e contagens para comparar nomes entre redes."""

    if not text:
        return ""
    text = _prepare(text)
    cleaned = _MULTIPLIER_RE.sub(" ", text)
    cleaned = _SIZE_RE.sub(" ", cleaned)
    for pattern in _COUNT_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return cleaned


def _decimal(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def format_size(package_size: float | None, package_unit: str | None) -> str:
    if package_size is None or package_unit is None:
        return "—"
    if package_unit == "kg" and package_size < 1:
        grams = package_size * 1000
        if grams < 1:
            return f"{_decimal(grams * 1000)} mg"
        return f"{_decimal(grams)} g"
    if package_unit == "l" and package_size < 1:
        return f"{_decimal(package_size * 1000)} ml"
    display_unit = "L" if package_unit == "l" else package_unit
    return f"{_decimal(package_size)} {display_unit}"


def format_unit_price(unit_price: float | None, package_unit: str | None) -> str:
    if unit_price is None or package_unit is None:
        return "—"
    value = f"{unit_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    display_unit = {"l": "L"}.get(package_unit, package_unit)
    return f"R$ {value}/{display_unit}"
