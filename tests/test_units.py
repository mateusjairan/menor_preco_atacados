from __future__ import annotations

import pytest

from src.units import (
    compute_unit_price,
    format_size,
    format_unit_price,
    parse_package,
    strip_size,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Leite Integral 1l", (1.0, "l")),
        ("Arroz 5kg", (5.0, "kg")),
        ("Pacote 500g", (0.5, "kg")),
        ("900ml", (0.9, "l")),
        ("30un", (30.0, "un")),
        ("1,5l", (1.5, "l")),
        ("1.5 L", (1.5, "l")),
        ("500 mg", (0.0005, "kg")),
        ("Leite 1 litro", (1.0, "l")),
        ("Leite 1l caixa 12un", (12.0, "l")),
        ("Detergente 500ml", (0.5, "l")),
        ("Produto sem tamanho", (None, None)),
        ("", (None, None)),
    ],
)
def test_parse_package(text, expected):
    assert parse_package(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Refrigerante Coca-Cola Lata 350ml com 6 Unidades", (2.1, "l")),
        (
            "Refrigerante Coca-Cola Lata Pack c/ 6 Unid de 350ml Cada",
            (2.1, "l"),
        ),
        ("Refrigerante Coca Cola Pack C6 350ml", (2.1, "l")),
        ("Coca-Cola 6 x 350ml", (2.1, "l")),
        ("Coca-Cola 6x350ml", (2.1, "l")),
        ("Coca-Cola 2x2L", (4.0, "l")),
        ("Coca-Cola 12 x 1 L", (12.0, "l")),
        ("Coca-Cola 350ml Leve 6 Pague 5", (2.1, "l")),
        ("Coca-Cola 6 latas 350ml", (2.1, "l")),
        ("Coca-Cola 350ml 6un", (2.1, "l")),
        ("Coca-Cola 2L Pack 6", (12.0, "l")),
        ("Coca-Cola Pack 2L", (None, None)),
        ("Kit Coca-Cola 2l + Fanta 2 Litros", (4.0, "l")),
        ("Coca-Cola 2l e Fanta 2l", (4.0, "l")),
        ("Coca-Cola 2l + 6 unidades de 350ml", (4.1, "l")),
        ("Coca-Cola 2,5 Litros", (2.5, "l")),
        ("Copos descartáveis 30un", (30.0, "un")),
        ("Coca-Cola 6 unidades", (6.0, "un")),
        ("Refrigerante 2 litros", (2.0, "l")),
        ("Refrigerante 500 mililitros", (0.5, "l")),
        ("Refrigerante 2 lt", (2.0, "l")),
        ("Arroz 1 quilograma", (1.0, "kg")),
        ("Queijo 500 gramas", (0.5, "kg")),
        ("Papel Higiênico 30m com 12 rolos", (12.0, "un")),
        ("Papel Higiênico 30m Leve 16 Pague 15 Unid", (16.0, "un")),
        (
            "Detergente Pato 40g Cada Leve 3 Pague 2 Unid",
            (0.12, "kg"),
        ),
        (
            "Detergente Pato 40g Cada Leve3Pague 2 Unid",
            (0.12, "kg"),
        ),
        ("Papel Higiênico 30m Leve 24 Pague 22", (24.0, "un")),
        ("Papel Higiênico 30m Leve 12 Pague 11 Unidades", (12.0, "un")),
        ("Papel Higiênico Neve 20m Leve 16 Pague 1596g", (16.0, "un")),
        ("Papel Higiênico 30m com 12 rolos", (12.0, "un")),
        ("Papel Higiênico 12 Rolos 96g", (12.0, "un")),
        ("Papel Toalha 2 rolos 100g", (2.0, "un")),
        (
            "Papel Higiênico 30m Leve 12 Rolos Pague 11 Rolos",
            (12.0, "un"),
        ),
        ("Água Sanitária Leve 1l Pague 900ml", (1.0, "l")),
        ("Água Sanitária Leve 5l Pague 4,5 Litros", (5.0, "l")),
        ("Enxaguante Bucal Leve 500ml Pague 300ml", (0.5, "l")),
        ("Enxaguante Bucal Leve 500 Pague 350ml", (0.5, "l")),
        ("Enxaguante Bucal Leve 500 Pague 300ml", (0.5, "l")),
        ("Enxaguante Bucal Leve 1l Pague 900ml", (1.0, "l")),
        ("Pack de 6 350ml", (2.1, "l")),
        ("Cerveja Fardo com 12 Latas 350ml", (4.2, "l")),
        ("Cerveja Multipack 15x269ml", (4.035, "l")),
        ("Pack 500ml", (None, None)),
        ("Pack Refrigerante Coca Cola Fanta Laranja 2L", (None, None)),
        ("Cerveja Budweiser Multipack LT 350ml", (None, None)),
        ("Alfajor Multipack Chocolate 50g", (None, None)),
        ("Fardo Cerveja 350ml", (None, None)),
        ("Café Santa Clara Premium Stand Pack 250g", (0.25, "kg")),
        ("Picolé Bacio di Latte Chocolate Belga70g", (0.07, "kg")),
        ("Óleo Gallo Limão Siciliano Vidro250ml", (0.25, "l")),
        ("Condicionador Johnsons Frasco200ml", (0.2, "l")),
        ("Inseticida Baygon 360mlEmbalagem Econômica", (0.36, "l")),
        ("Iogurte Batavo 1 ,15KgEmbalagem Econômica", (1.15, "kg")),
        ("Detergente Pato Refil 38gOferta Especial", (0.038, "kg")),
        ("Óleo Liza Algodão 900mll", (0.9, "l")),
        ("Papel Higiênico Dama 30m LV 24 PG 22 rolos", (24.0, "un")),
        ("Papel Higiênico Neve 30m LV 32 PG 28 rolos", (32.0, "un")),
        ("Enxaguante Listerine Zero L500P350ml", (0.5, "l")),
        ("Cerveja 6-pack 350ml", (2.1, "l")),
        ("Cerveja 12 pack 269ml", (3.228, "l")),
    ],
)
def test_parse_multipack(text, expected):
    assert parse_package(text) == expected


def test_multipack_unit_price_matches_total_content():
    # 6 latas de 350 ml por R$ 22,49 = 2,1 L -> R$ 10,71/L.
    price = 22.49
    size, unit = parse_package("Coca-Cola Lata 350ml com 6 Unidades")
    assert (size, unit) == (2.1, "l")
    assert compute_unit_price(price, size) == pytest.approx(10.7095, rel=1e-3)


def test_single_bottle_is_not_multiplied():
    size, unit = parse_package("Coca-Cola Pet 2L")
    assert (size, unit) == (2.0, "l")
    assert compute_unit_price(10.0, size) == 5.0


def test_unit_price_1kg_vs_500g():
    price_1kg = compute_unit_price(10.0, 1.0)
    price_500g = compute_unit_price(4.0, 0.5)
    assert price_1kg == 10.0
    assert price_500g == 8.0
    assert price_500g < price_1kg


def test_unit_price_900ml_vs_1l():
    ninety = compute_unit_price(10.0, 0.9)
    one_liter = compute_unit_price(10.0, 1.0)
    assert ninety > one_liter


def test_unit_price_without_size_is_none():
    assert compute_unit_price(5.0, None) is None
    assert compute_unit_price(None, 1.0) is None


def test_strip_size():
    assert strip_size("Leite Integral 1l").split() == ["Leite", "Integral"]
    assert "1l" not in strip_size("Leite 1l")


def test_formatters():
    assert format_size(1.0, "l") == "1 L"
    assert format_size(1.5, "l") == "1,5 L"
    assert format_size(0.5, "kg") == "500 g"
    assert format_size(0.045, "kg") == "45 g"
    assert format_size(0.0005, "kg") == "500 mg"
    assert format_size(0.9, "l") == "900 ml"
    assert format_size(None, None) == "—"
    assert format_unit_price(9.98, "l") == "R$ 9,98/L"
    assert format_unit_price(None, "l") == "—"
