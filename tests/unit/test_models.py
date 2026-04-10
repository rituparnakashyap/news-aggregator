from __future__ import annotations

from datetime import datetime, timezone

import pytest

from news_aggregator.models.article import Article, ArticleSource, _make_id
from news_aggregator.models.result import AggregatedResult, CategoryResult


def _make_source(adapter: str = "newsapi") -> ArticleSource:
    return ArticleSource(adapter_name=adapter, source_id="test-source", url="https://example.com")


def _make_article(**kwargs) -> Article:
    defaults = dict(
        title="Test Article",
        url="https://example.com/article",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        category="technology",
        source=_make_source(),
    )
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# Article ID generation
# ---------------------------------------------------------------------------

def test_article_id_auto_generated():
    a = _make_article()
    assert len(a.id) == 16
    assert a.id.isalnum()


def test_article_id_deterministic():
    a1 = _make_article()
    a2 = _make_article()
    assert a1.id == a2.id


def test_articles_with_same_title_and_url_get_same_id():
    a1 = _make_article(title="Breaking News", url="https://foo.com/news")
    a2 = _make_article(title="Breaking News", url="https://foo.com/news")
    assert a1.id == a2.id


def test_articles_with_different_urls_get_different_ids():
    a1 = _make_article(url="https://foo.com/a")
    a2 = _make_article(url="https://foo.com/b")
    assert a1.id != a2.id


def test_article_id_case_insensitive_on_title():
    a1 = _make_article(title="Breaking News")
    a2 = _make_article(title="BREAKING NEWS")
    assert a1.id == a2.id


def test_explicit_id_not_overwritten():
    a = _make_article(id="custom-id-1234567")
    assert a.id == "custom-id-1234567"


# ---------------------------------------------------------------------------
# Article default values
# ---------------------------------------------------------------------------

def test_article_defaults():
    a = _make_article()
    assert a.mention_count == 1
    assert a.description is None
    assert a.content_snippet is None


# ---------------------------------------------------------------------------
# CategoryResult and AggregatedResult
# ---------------------------------------------------------------------------

def test_category_result_fields():
    articles = [_make_article()]
    result = CategoryResult(
        category="technology",
        articles=articles,
        headline="Tech News Today",
        summaries=["Line one.", "Line two.", "Line three."],
        rendered_text="Tech News Today\n1. Line one.\n2. Line two.\n3. Line three.\n",
    )
    assert result.category == "technology"
    assert len(result.articles) == 1
    assert result.headline == "Tech News Today"
    assert result.summaries == ["Line one.", "Line two.", "Line three."]


def test_aggregated_result_fields():
    now = datetime.now(timezone.utc)
    cat_result = CategoryResult(
        category="technology",
        articles=[],
        headline="headline",
        summaries=["summary"],
        rendered_text="headline\n1. summary\n",
    )
    agg = AggregatedResult(
        generated_at=now,
        lookback_hours=24,
        categories=[cat_result],
    )
    assert agg.lookback_hours == 24
    assert len(agg.categories) == 1
    assert agg.generated_at == now
