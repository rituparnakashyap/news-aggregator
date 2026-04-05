from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import httpx

if TYPE_CHECKING:
    from news_aggregator.config.schema import SourceConfig
    from news_aggregator.models.article import Article


class SourceError(Exception):
    pass


class RateLimitError(SourceError):
    pass


class BaseNewsSource(ABC):
    name: ClassVar[str]

    def __init__(
        self,
        api_key: str | None,
        config: "SourceConfig",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.config = config
        # Allow injecting a client for testing; otherwise create a shared one lazily
        self._client = client

    @abstractmethod
    async def fetch(
        self,
        category: str,
        lookback_hours: int,
        max_results: int = 100,
    ) -> list["Article"]:
        """Fetch articles for one category within the lookback window."""
        ...

    async def _get(self, url: str, params: dict) -> dict:
        """Shared GET helper with basic error mapping."""
        if self._client is None:
            raise RuntimeError("No httpx client — call fetch() via an async context")
        try:
            response = await self._client.get(url, params=params, timeout=15.0)
        except httpx.TimeoutException as e:
            raise SourceError(f"[{self.name}] Request timed out: {url}") from e
        except httpx.RequestError as e:
            raise SourceError(f"[{self.name}] Request error: {e}") from e

        if response.status_code == 429:
            raise RateLimitError(f"[{self.name}] Rate limit exceeded")
        if response.status_code >= 500:
            raise SourceError(f"[{self.name}] Server error {response.status_code}")
        if response.status_code >= 400:
            raise SourceError(
                f"[{self.name}] Client error {response.status_code}: {response.text[:200]}"
            )

        return response.json()
