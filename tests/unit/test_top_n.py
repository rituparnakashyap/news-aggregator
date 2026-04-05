from __future__ import annotations

from datetime import datetime, timezone

import pytest

from news_aggregator.aggregation.top_n import TopNStrategy
from news_aggregator.aggregation.base import StrategyError
from news_aggregator.aggregation.registry import get_strategy
from news_aggregator.models.article import Article, ArticleSource
import news_aggregator.aggregation  # noqa: F401 — trigger registration


def _article(title: str, n: int = 0) -> Article:
    return Article(
        title=title,
        url=f"https://foo.com/{n}",
        published_at=datetime.now(timezone.utc),
        category="tech",
        source=ArticleSource(adapter_name="newsapi", source_id="src", url="https://x.com"),
    )


def _articles(count: int) -> list[Article]:
    return [_article(f"Article {i}", i) for i in range(count)]


def test_returns_top_n():
    articles = _articles(10)
    result = TopNStrategy().select(articles, {"n": 5})
    assert len(result) == 5
    assert result == articles[:5]


def test_fewer_than_n_articles():
    articles = _articles(3)
    result = TopNStrategy().select(articles, {"n": 5})
    assert len(result) == 3


def test_exactly_n_articles():
    articles = _articles(5)
    result = TopNStrategy().select(articles, {"n": 5})
    assert len(result) == 5


def test_n_equals_one():
    articles = _articles(10)
    result = TopNStrategy().select(articles, {"n": 1})
    assert len(result) == 1


def test_missing_n_raises():
    with pytest.raises(StrategyError, match="requires 'n'"):
        TopNStrategy().select(_articles(5), {})


def test_n_less_than_one_raises():
    with pytest.raises(StrategyError):
        TopNStrategy().select(_articles(5), {"n": 0})


def test_registry_returns_top_n():
    cls = get_strategy("TopN")
    assert cls is TopNStrategy
