from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_aggregator.config.schema import (
    AggregationConfig,
    AppConfig,
    CategoryConfig,
    LLMConfig,
    SourceConfig,
)
from news_aggregator.models.article import Article, ArticleSource
from news_aggregator.models.result import AggregatedResult
from news_aggregator.pipeline import Pipeline


def _make_config(strategy: str = "TopN", n: int = 3) -> AppConfig:
    return AppConfig(
        sources=[
            SourceConfig(name="newsapi", enabled=True),
            SourceConfig(name="guardian", enabled=True),
            SourceConfig(name="gdelt", enabled=False),
        ],
        categories=[
            CategoryConfig(name="technology"),
            CategoryConfig(name="finance"),
        ],
        aggregation=AggregationConfig(
            strategy=strategy,
            params={"n": n},
            lookback_hours=24,
            dedup_threshold=0.85,
        ),
        llm=LLMConfig(model="gpt-4o-mini", headline_max_chars=100, summary_max_lines=3),
        output_format="text",
    )


def _make_articles(category: str, count: int = 5, prefix: str = "src") -> list[Article]:
    return [
        Article(
            title=f"{category.title()} News {i} from {prefix}",
            url=f"https://{prefix}.com/{category}/{i}",
            published_at=datetime(2024, 6, 1, i, 0, tzinfo=timezone.utc),
            category=category,
            source=ArticleSource(adapter_name=prefix, source_id=prefix, url=f"https://{prefix}.com"),
            description=f"Description of {category} article {i}",
        )
        for i in range(count)
    ]


def _mock_llm_completion(headline: str = "Test Headline", summaries: list[str] | None = None):
    if summaries is None:
        summaries = ["Line 1.", "Line 2.", "Line 3."]
    content = json.dumps({"headline": headline, "summaries": summaries})
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return AsyncMock(return_value=mock_response)


ENV = {
    "LLM_API_KEY": "test-key",
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "NEWSAPI_KEY": "newsapi-key",
    "GUARDIAN_KEY": "guardian-key",
}


@pytest.mark.asyncio
async def test_pipeline_runs_and_returns_aggregated_result():
    cfg = _make_config()

    tech_articles = _make_articles("technology", 5, "newsapi")
    fin_articles = _make_articles("finance", 5, "guardian")

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(return_value=tech_articles)),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=fin_articles)),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=_mock_llm_completion()))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    assert isinstance(result, AggregatedResult)
    assert len(result.categories) == 2
    assert result.lookback_hours == 24


@pytest.mark.asyncio
async def test_pipeline_category_names_correct():
    cfg = _make_config()

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(return_value=_make_articles("technology"))),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=_make_articles("finance"))),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=_mock_llm_completion()))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    names = {c.category for c in result.categories}
    assert "technology" in names
    assert "finance" in names


@pytest.mark.asyncio
async def test_pipeline_applies_top_n_strategy():
    cfg = _make_config(strategy="TopN", n=3)

    articles = _make_articles("technology", 10)

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(return_value=articles)),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=[])),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=_mock_llm_completion()))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    tech = next(c for c in result.categories if c.category == "technology")
    assert len(tech.articles) <= 3


@pytest.mark.asyncio
async def test_pipeline_graceful_degradation_on_source_failure():
    """One source failing should not crash the whole category."""
    cfg = _make_config()

    from news_aggregator.sources.base import SourceError

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(side_effect=SourceError("down"))),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=_make_articles("technology", 5))),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=_mock_llm_completion()))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    tech = next((c for c in result.categories if c.category == "technology"), None)
    assert tech is not None
    assert len(tech.articles) > 0


@pytest.mark.asyncio
async def test_pipeline_llm_called_once_per_category():
    cfg = _make_config()

    llm_create = _mock_llm_completion()

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(return_value=_make_articles("technology"))),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=_make_articles("finance"))),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=llm_create))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    # 2 categories => LLM called twice
    assert llm_create.call_count == 2


@pytest.mark.asyncio
async def test_pipeline_category_headline_and_summary_set():
    cfg = _make_config()

    with (
        patch("news_aggregator.sources.newsapi.NewsApiSource.fetch", new=AsyncMock(return_value=_make_articles("technology"))),
        patch("news_aggregator.sources.guardian.GuardianSource.fetch", new=AsyncMock(return_value=[])),
        patch(
            "news_aggregator.llm.client.AsyncOpenAI",
            return_value=MagicMock(
                chat=MagicMock(completions=MagicMock(create=_mock_llm_completion("Test Headline", ["L1.", "L2.", "L3."])))
            ),
        ),
    ):
        result = await Pipeline(cfg, ENV).run()

    tech = next(c for c in result.categories if c.category == "technology")
    assert tech.headline == "Test Headline"
    assert tech.summaries == ["L1.", "L2.", "L3."]
    assert tech.rendered_text != ""
    assert "L1." in tech.rendered_text
