from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from news_aggregator.aggregation.top_n_lucky_m import TopNLuckyMStrategy
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


def test_result_length_is_n():
    articles = _articles(20)
    result = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 2})
    assert len(result) == 5


def test_m_slots_from_lower_pool():
    random.seed(42)
    articles = _articles(20)
    top_urls = {a.url for a in articles[:5]}
    lower_urls = {a.url for a in articles[5:]}

    result = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 2})
    result_urls = {a.url for a in result}

    lucky = result_urls & lower_urls
    assert len(lucky) == 2


def test_m_zero_equivalent_to_top_n():
    articles = _articles(20)
    result = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 0})
    assert result == articles[:5]


def test_fewer_lower_articles_than_m():
    # Only 2 articles beyond top-5, but m=3 requested
    articles = _articles(7)  # top-5 + 2 lower
    result = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 3})
    # Should return 5: 3 deterministic top + 2 lucky (all available lower)
    assert len(result) == 5


def test_missing_n_raises():
    with pytest.raises(StrategyError, match="requires 'n'"):
        TopNLuckyMStrategy().select(_articles(10), {"m": 2})


def test_missing_m_raises():
    with pytest.raises(StrategyError, match="requires 'm'"):
        TopNLuckyMStrategy().select(_articles(10), {"n": 5})


def test_m_equals_n_raises():
    with pytest.raises(StrategyError, match="must be < 'n'"):
        TopNLuckyMStrategy().select(_articles(10), {"n": 5, "m": 5})


def test_m_greater_than_n_raises():
    with pytest.raises(StrategyError, match="must be < 'n'"):
        TopNLuckyMStrategy().select(_articles(10), {"n": 5, "m": 6})


def test_m_negative_raises():
    with pytest.raises(StrategyError):
        TopNLuckyMStrategy().select(_articles(10), {"n": 5, "m": -1})


def test_registry_returns_top_n_lucky_m():
    cls = get_strategy("TopNLuckyM")
    assert cls is TopNLuckyMStrategy


def test_deterministic_with_seed():
    random.seed(0)
    articles = _articles(20)
    r1 = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 2})
    random.seed(0)
    r2 = TopNLuckyMStrategy().select(articles, {"n": 5, "m": 2})
    assert [a.url for a in r1] == [a.url for a in r2]
