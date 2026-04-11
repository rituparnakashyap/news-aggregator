from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import httpx

if TYPE_CHECKING:
    from news_aggregator.config.schema import SourceConfig
    from news_aggregator.models.article import Article

logger = logging.getLogger(__name__)


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
        """GET with exponential backoff retry (3 attempts) for transient errors."""
        return await self._fetch_with_retry(url, params, max_retries=3, backoff=1.5)

    async def _fetch_with_retry(
        self,
        url: str,
        params: dict,
        max_retries: int = 3,
        backoff: float = 1.5,
    ) -> dict:
        if self._client is None:
            raise RuntimeError("No httpx client — call fetch() via an async context")

        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self._client.get(url, params=params, timeout=15.0)
            except httpx.TimeoutException as e:
                last_exc = SourceError(f"[{self.name}] Request timed out: {url}")
                logger.warning("%s (attempt %d/%d)", last_exc, attempt + 1, max_retries)
            except httpx.RequestError as e:
                raise SourceError(f"[{self.name}] Request error: {e}") from e
            else:
                if response.status_code == 429:
                    raise RateLimitError(f"[{self.name}] Rate limit exceeded")
                if response.status_code >= 500:
                    last_exc = SourceError(f"[{self.name}] Server error {response.status_code}")
                    logger.warning("%s (attempt %d/%d)", last_exc, attempt + 1, max_retries)
                elif response.status_code >= 400:
                    raise SourceError(
                        f"[{self.name}] Client error {response.status_code}: {response.text[:200]}"
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as e:
                        raise SourceError(
                            f"[{self.name}] Invalid JSON in response "
                            f"(status {response.status_code}, body: {response.text[:100]!r})"
                        ) from e

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff ** attempt)

        raise last_exc or SourceError(f"[{self.name}] All {max_retries} retries exhausted")
