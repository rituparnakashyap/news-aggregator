from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from news_aggregator.config.schema import SourceConfig
from news_aggregator.models.article import Article, ArticleSource
from news_aggregator.sources.base import BaseNewsSource, SourceError
from news_aggregator.sources.registry import register

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

_CATEGORY_QUERIES: dict[str, str] = {
    "technology": "technology OR artificial intelligence OR software",
    "finance": "finance OR economy OR stock market OR business",
    "sports": "sports OR football OR basketball OR soccer",
    "politics": "politics OR election OR government OR policy",
    "health": "health OR medicine OR disease OR vaccine",
    "science": "science OR research OR climate OR space",
    "entertainment": "entertainment OR movies OR music",
    "world": "world news OR international",
}


@register
class GdeltSource(BaseNewsSource):
    name = "gdelt"

    # GDELT requires no API key
    def __init__(
        self,
        api_key: str | None,
        config: SourceConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key=None, config=config, client=client)

    async def fetch(
        self,
        category: str,
        lookback_hours: int,
        max_results: int = 100,
    ) -> list[Article]:
        query = _CATEGORY_QUERIES.get(category, category)
        start_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        params = {
            "query": f"{query} sourcelang:english",
            "mode": "artlist",
            "maxrecords": min(max_results, 250),
            "startdatetime": start_dt.strftime("%Y%m%d%H%M%S"),
            "format": "json",
        }

        data = await self._get(_BASE_URL, params)

        articles = []
        for raw in data.get("articles", []):
            article = self._normalize(raw, category)
            if article:
                articles.append(article)

        return articles

    def _normalize(self, raw: dict, category: str) -> Article | None:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()

        if not title or not url:
            return None

        seendate = raw.get("seendate", "")
        try:
            # GDELT format: YYYYMMDDTHHmmssZ
            published_at = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, AttributeError):
            published_at = datetime.now(timezone.utc)

        domain = raw.get("domain") or url

        return Article(
            title=title,
            url=url,
            published_at=published_at,
            category=category,
            source=ArticleSource(
                adapter_name=self.name,
                source_id=domain,
                url=url,
            ),
            description=None,
            content_snippet=None,
        )
