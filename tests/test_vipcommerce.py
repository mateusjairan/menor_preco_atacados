from __future__ import annotations

import pytest

from src import config
from src.adapters.base import AdapterError
from src.adapters.vipcommerce import VipCommerceAdapter
from src.aggregator import build_adapters


def test_reverse_api_is_disabled_by_default():
    assert config.ENABLE_REVERSE_API is False


def test_vipcommerce_is_not_homologated():
    adapter = VipCommerceAdapter(config.TIER_B[0])
    with pytest.raises(AdapterError, match="não homologada"):
        adapter.fetch("leite")


def test_reverse_adapters_are_not_built_when_flag_is_off(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_REVERSE_API", False)
    adapters = build_adapters(include_reverse=True)
    assert all(adapter.chain.access == "public" for adapter in adapters)
