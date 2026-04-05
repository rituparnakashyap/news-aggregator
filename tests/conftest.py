from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from news_aggregator.config.schema import (
    AggregationConfig,
    AppConfig,
    CategoryConfig,
    LLMConfig,
    SourceConfig,
)
from news_aggregator.models.article import Article, ArticleSource
from news_aggregator.models.result import AggregatedResult, CategoryResult


@pytest.fixture
def sample_source() -> ArticleSource:
    return ArticleSource(adapter_name="newsapi", source_id="test-source", url="https://example.com")


@pytest.fixture
def sample_articles(sample_source) -> list[Article]:
    return [
        Article(
            title=f"Sample Article {i}",
            url=f"https://example.com/article/{i}",
            published_at=datetime(2024, 6, 1, i, 0, tzinfo=timezone.utc),
            category="technology",
            source=sample_source,
            description=f"Description of article {i}",
            content_snippet=f"Content snippet for article {i}",
            mention_count=10 - i,  # descending mention counts
        )
        for i in range(10)
    ]


@pytest.fixture
def minimal_config() -> AppConfig:
    return AppConfig(
        sources=[
            SourceConfig(name="newsapi", enabled=True),
            SourceConfig(name="guardian", enabled=True),
        ],
        categories=[
            CategoryConfig(name="technology"),
        ],
        aggregation=AggregationConfig(
            strategy="TopN",
            params={"n": 5},
            lookback_hours=24,
            dedup_threshold=0.85,
        ),
        llm=LLMConfig(model="gpt-4o-mini", headline_max_chars=100, summary_max_lines=3),
        output_format="text",
    )


@pytest.fixture
def mock_llm_response() -> MagicMock:
    """Returns a mock OpenAI completion response with a canned headline/summary."""
    content = json.dumps({
        "headline": "Tech Industry Sees Major Shift",
        "summary": "The technology sector experienced significant changes.\nNew developments emerged across multiple areas.\nExperts predict continued growth.",
    })
    mock = MagicMock()
    mock.choices[0].message.content = content
    return mock


@pytest.fixture
def sample_aggregated_result() -> AggregatedResult:
    source = ArticleSource(adapter_name="newsapi", source_id="src", url="https://example.com")
    articles = [
        Article(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            published_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            category="technology",
            source=source,
        )
        for i in range(3)
    ]
    return AggregatedResult(
        generated_at=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
        lookback_hours=24,
        categories=[
            CategoryResult(
                category="technology",
                articles=articles,
                headline="Tech News Today",
                summary="Line one.\nLine two.\nLine three.",
            ),
            CategoryResult(
                category="finance",
                articles=[],
                headline="Finance Market Update",
                summary="Markets moved today.\nVolatility continued.\nAnalysts weigh in.",
            ),
        ],
    )
