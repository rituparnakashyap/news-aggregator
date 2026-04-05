from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from news_aggregator.config.schema import SourceConfig
from news_aggregator.models.article import Article, ArticleSource
from news_aggregator.sources.base import BaseNewsSource, SourceError
from news_aggregator.sources.registry import register

_BASE_URL = "https://content.guardianapis.com/search"

_CATEGORY_SECTIONS: dict[str, str] = {
    "technology": "technology",
    "finance": "business",
    "sports": "sport",
    "politics": "politics",
    "health": "society",
    "science": "science",
    "entertainment": "culture",
    "world": "world",
}


@register
class GuardianSource(BaseNewsSource):
    name = "guardian"

    def __init__(
        self,
        api_key: str | None,
        config: SourceConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key, config, client)
        if not api_key:
            raise SourceError("[guardian] GUARDIAN_KEY is required")

    async def fetch(
        self,
        category: str,
        lookback_hours: int,
        max_results: int = 100,
    ) -> list[Article]:
        section = _CATEGORY_SECTIONS.get(category, category)
        from_dt = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        params = {
            "section": section,
            "from-date": from_dt.strftime("%Y-%m-%d"),
            "page-size": min(max_results, 50),
            "show-fields": "trailText,bodyText",
            "order-by": "newest",
            "api-key": self.api_key,
        }

        data = await self._get(_BASE_URL, params)

        response = data.get("response", {})
        if response.get("status") != "ok":
            raise SourceError(f"[guardian] API error: {data}")

        articles = []
        for raw in response.get("results", []):
            article = self._normalize(raw, category)
            if article:
                articles.append(article)

        return articles

    def _normalize(self, raw: dict, category: str) -> Article | None:
        title = (raw.get("webTitle") or "").strip()
        url = (raw.get("webUrl") or "").strip()

        if not title or not url:
            return None

        published_str = raw.get("webPublicationDate", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published_at = datetime.now(timezone.utc)

        fields = raw.get("fields") or {}
        description = fields.get("trailText") or None
        body = fields.get("bodyText") or ""
        snippet = (body[:500] or description or "")[:500] or None

        return Article(
            title=title,
            url=url,
            published_at=published_at,
            category=category,
            source=ArticleSource(
                adapter_name=self.name,
                source_id="the-guardian",
                url="https://www.theguardian.com",
            ),
            description=description,
            content_snippet=snippet,
        )
