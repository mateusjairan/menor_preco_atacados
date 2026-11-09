from __future__ import annotations

from src.matching import (
    GROUP_THRESHOLD,
    SIMILAR_THRESHOLD,
    best_in_group,
    group_products,
    match_score,
    name_without_size,
    similar_group_count,
)


def test_same_ean_groups_across_chains(make_product):
    left = make_product(chain="GBarbosa", chain_slug="gbarbosa", ean="7891000")
    right = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        name="Leite Integral Outra Marca 1l",
        ean="7891000",
    )
    groups = group_products([left, right])
    assert len(groups) == 1
    assert match_score(left, right) == 100.0
    assert len(groups[0].products) == 2


def test_different_ean_does_not_group(make_product):
    left = make_product(ean="111")
    right = make_product(chain="Atacadão", chain_slug="atacadao", ean="222")
    assert len(group_products([left, right])) == 2


def test_fuzzy_threshold_85_groups(monkeypatch, make_product):
    monkeypatch.setattr("src.matching.fuzz.token_set_ratio", lambda *_: GROUP_THRESHOLD)
    left = make_product(name="Leite Integral Marca A 1l")
    right = make_product(
        chain="Atacadão", chain_slug="atacadao", name="Leite Integral Marca B 1l"
    )
    groups = group_products([left, right])
    assert len(groups) == 1
    assert groups[0].similar is False


def test_fuzzy_50_does_not_group(monkeypatch, make_product):
    monkeypatch.setattr("src.matching.fuzz.token_set_ratio", lambda *_: 50.0)
    left = make_product(name="Leite Integral Marca A 1l")
    right = make_product(chain="Atacadão", chain_slug="atacadao", name="Sabao em Po 1l")
    groups = group_products([left, right])
    assert len(groups) == 2


def test_similar_60_to_84_groups_with_warning(monkeypatch, make_product):
    monkeypatch.setattr("src.matching.fuzz.token_set_ratio", lambda *_: 70.0)
    left = make_product(name="Leite Integral Marca A 1l")
    right = make_product(
        chain="Atacadão", chain_slug="atacadao", name="Leite Integral Marca B 1l"
    )
    groups = group_products([left, right])
    assert len(groups) == 1
    assert groups[0].similar is True
    assert similar_group_count(groups) == 1


def test_different_sizes_never_group(make_product):
    left = make_product(name="Arroz Tipo 1 1kg", package_size=1.0, package_unit="kg")
    right = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        name="Arroz Tipo 1 500g",
        package_size=0.5,
        package_unit="kg",
    )
    assert match_score(left, right) == 0.0
    assert len(group_products([left, right])) == 2


def test_missing_size_does_not_group_with_known_size(make_product):
    left = make_product(name="Detergente Neutro", package_size=None, package_unit=None)
    right = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        name="Detergente Neutro 500ml",
        package_size=0.5,
        package_unit="l",
    )
    assert len(group_products([left, right])) == 2


def test_best_in_group_uses_unit_price(make_product):
    expensive = make_product(
        chain="GBarbosa",
        chain_slug="gbarbosa",
        name="Arroz Tipo 1 1kg",
        price=10.0,
        package_size=1.0,
        package_unit="kg",
    )
    cheap = make_product(
        chain="Atacadão",
        chain_slug="atacadao",
        name="Arroz Tipo 1 1kg",
        price=8.0,
        package_size=1.0,
        package_unit="kg",
    )
    groups = group_products([expensive, cheap])
    assert len(groups) == 1
    assert best_in_group(groups[0]) is cheap


def test_name_normalization():
    assert name_without_size("Leite  Integral 1L") == "leite integral"
    assert name_without_size("AÇÃO 1kg") == "acao"
    assert SIMILAR_THRESHOLD < GROUP_THRESHOLD
