from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from news_aggregator.aggregation.base import BaseStrategy

_REGISTRY: dict[str, type["BaseStrategy"]] = {}


def register(cls: type["BaseStrategy"]) -> type["BaseStrategy"]:
    """Class decorator that registers a strategy by its `name` attribute."""
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str) -> type["BaseStrategy"]:
    """Return a registered strategy class by name."""
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown aggregation strategy '{name}'. "
            f"Registered strategies: {list(_REGISTRY)}"
        )
    return _REGISTRY[name]
