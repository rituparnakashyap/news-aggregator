from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from news_aggregator.config.schema import SourceConfig
from news_aggregator.models.article import Article, ArticleSource
from news_aggregator.sources.base import BaseNewsSource, SourceError
from news_aggregator.sources.registry import register

_BASE_URL = "https://newsapi.org/v2/everything"

# NewsAPI category -> query keywords mapping
# NewsAPI's /v2/everything uses keyword search; /v2/top-headlines supports
# a limited set of categories. We use keyword search for broader coverage.
_CATEGORY_QUERIES: dict[str, str] = {
    "technology": "technology OR tech OR software OR AI OR artificial intelligence",
    "finance": "finance OR stock market OR economy OR business OR investing",
    "sports": "sports OR football OR basketball OR soccer OR tennis OR olympics",
    "politics": "politics OR government OR election OR policy OR congress OR parliament",
    "health": "health OR medicine OR medical OR healthcare OR disease OR vaccine",
    "science": "science OR research OR discovery OR physics OR biology OR climate",
    "entertainment": "entertainment OR movies OR music OR celebrity OR hollywood",
    "world": "world news OR international OR global",
}


@register
class NewsApiSource(BaseNewsSource):
    name = "newsapi"

    def __init__(
        self,
        api_key: str | None,
        config: SourceConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key, config, client)
        if not api_key:
            raise SourceError("[newsapi] NEWSAPI_KEY is required")

    async def fetch(
        self,
        category: str,
        lookback_hours: int,
        max_results: int = 100,
    ) -> list[Article]:
        query = _CATEGORY_QUERIES.get(category, category)
        from_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        params = {
            "q": query,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "language": "en",
            "pageSize": min(max_results, 100),
            "sortBy": "publishedAt",
            "apiKey": self.api_key,
        }

        data = await self._get(_BASE_URL, params)

        if data.get("status") != "ok":
            raise SourceError(f"[newsapi] API error: {data.get('message', 'unknown')}")

        articles = []
        for raw in data.get("articles", []):
            article = self._normalize(raw, category)
            if article:
                articles.append(article)

        return articles

    def _normalize(self, raw: dict, category: str) -> Article | None:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()

        if not title or not url or title == "[Removed]":
            return None

        published_str = raw.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published_at = datetime.now(timezone.utc)

        source_name = raw.get("source", {}).get("name") or "newsapi"
        source_url = raw.get("source", {}).get("id") or url

        description = raw.get("description") or None
        content = raw.get("content") or None
        snippet = (content or description or "")[:500] or None

        return Article(
            title=title,
            url=url,
            published_at=published_at,
            category=category,
            source=ArticleSource(
                adapter_name=self.name,
                source_id=source_name,
                url=source_url,
            ),
            description=description,
            content_snippet=snippet,
        )
