from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from news_aggregator.config.schema import SourceConfig
    from news_aggregator.sources.base import BaseNewsSource

_REGISTRY: dict[str, type["BaseNewsSource"]] = {}


def register(cls: type["BaseNewsSource"]) -> type["BaseNewsSource"]:
    """Class decorator that registers a source adapter by its `name` attribute."""
    _REGISTRY[cls.name] = cls
    return cls


def get_source(
    name: str,
    api_key: str | None,
    config: "SourceConfig",
    client: httpx.AsyncClient | None = None,
) -> "BaseNewsSource":
    """Instantiate a registered source adapter by name."""
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown news source '{name}'. Registered sources: {list(_REGISTRY)}"
        )
    return _REGISTRY[name](api_key=api_key, config=config, client=client)
