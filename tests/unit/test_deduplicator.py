from __future__ import annotations

from datetime import datetime, timezone

import pytest

from news_aggregator.aggregation.deduplicator import Deduplicator, _jaccard, _tokenize
from news_aggregator.models.article import Article, ArticleSource


def _src(name: str = "newsapi") -> ArticleSource:
    return ArticleSource(adapter_name=name, source_id="src", url="https://example.com")


def _article(title: str, url: str, *, ts: int = 1000, mention_count: int = 1) -> Article:
    return Article(
        title=title,
        url=url,
        published_at=datetime.fromtimestamp(ts, tz=timezone.utc),
        category="tech",
        source=_src(),
        mention_count=mention_count,
    )


# ---------------------------------------------------------------------------
# Tokenizer / Jaccard helpers
# ---------------------------------------------------------------------------

def test_tokenize_removes_stopwords():
    tokens = _tokenize("The quick brown fox")
    assert "the" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens


def test_tokenize_lowercases():
    tokens = _tokenize("BREAKING NEWS")
    assert "breaking" in tokens


def test_tokenize_removes_punctuation():
    tokens = _tokenize("hello, world!")
    assert "hello" in tokens
    assert "world" in tokens


def test_jaccard_identical():
    t = frozenset(["ai", "breakthrough"])
    assert _jaccard(t, t) == 1.0


def test_jaccard_disjoint():
    assert _jaccard(frozenset(["a"]), frozenset(["b"])) == 0.0


def test_jaccard_partial():
    a = frozenset(["ai", "chip", "news"])
    b = frozenset(["ai", "chip", "market"])
    assert 0 < _jaccard(a, b) < 1.0


# ---------------------------------------------------------------------------
# Deduplicator
# ---------------------------------------------------------------------------

def test_exact_dedup_by_id():
    a1 = _article("AI Breakthrough", "https://foo.com/ai")
    a2 = _article("AI Breakthrough", "https://foo.com/ai")  # same title + url = same id
    dedup = Deduplicator(threshold=0.99)
    result = dedup.deduplicate([a1, a2])
    assert len(result) == 1
    assert result[0].mention_count == 2


def test_exact_dedup_accumulates_mention_count():
    a1 = _article("AI Breakthrough", "https://foo.com/ai", mention_count=3)
    a2 = _article("AI Breakthrough", "https://foo.com/ai", mention_count=2)
    dedup = Deduplicator()
    result = dedup.deduplicate([a1, a2])
    assert result[0].mention_count == 5


def test_fuzzy_dedup_merges_near_duplicates():
    a1 = _article("Scientists Announce Major AI Breakthrough", "https://foo.com/a")
    a2 = _article("Scientists Announce Major AI Breakthrough Today", "https://bar.com/b")
    dedup = Deduplicator(threshold=0.7)
    result = dedup.deduplicate([a1, a2])
    assert len(result) == 1
    assert result[0].mention_count == 2


def test_different_articles_not_merged():
    a1 = _article("Stock Market Rally", "https://foo.com/a")
    a2 = _article("Scientists Discover New Planet", "https://bar.com/b")
    dedup = Deduplicator(threshold=0.85)
    result = dedup.deduplicate([a1, a2])
    assert len(result) == 2


def test_sorted_by_mention_count_desc():
    a1 = _article("Popular Article", "https://foo.com/a", mention_count=1)
    a2 = _article("Viral Story", "https://bar.com/b", mention_count=5)
    a3 = _article("Medium Story", "https://baz.com/c", mention_count=3)
    dedup = Deduplicator()
    result = dedup.deduplicate([a1, a2, a3])
    counts = [r.mention_count for r in result]
    assert counts == sorted(counts, reverse=True)


def test_sorted_by_published_at_when_count_equal():
    older = _article("Old News", "https://foo.com/a", ts=500)
    newer = _article("New News", "https://bar.com/b", ts=1000)
    dedup = Deduplicator()
    result = dedup.deduplicate([older, newer])
    # newer should come first (higher timestamp = later = desc sort)
    assert result[0].url == "https://bar.com/b"


def test_dedup_keeps_earliest_published_at_on_merge():
    a1 = _article("AI Breakthrough Today", "https://foo.com/a", ts=1000)
    a2 = _article("AI Breakthrough Today Latest", "https://bar.com/b", ts=500)
    dedup = Deduplicator(threshold=0.6)
    result = dedup.deduplicate([a1, a2])
    if len(result) == 1:
        assert result[0].published_at.timestamp() == 500


def test_dedup_fills_missing_description():
    a1 = _article("AI News", "https://foo.com/a")
    a1.description = None
    a2 = _article("AI News", "https://foo.com/a")
    a2.description = "A description of the AI news."
    dedup = Deduplicator()
    result = dedup.deduplicate([a1, a2])
    assert result[0].description == "A description of the AI news."


def test_dedup_single_article_unchanged():
    a = _article("Solo Article", "https://foo.com/solo")
    dedup = Deduplicator()
    result = dedup.deduplicate([a])
    assert len(result) == 1
    assert result[0].mention_count == 1


def test_dedup_empty_list():
    dedup = Deduplicator()
    assert dedup.deduplicate([]) == []


def test_result_length_never_exceeds_input():
    articles = [_article(f"Article {i}", f"https://foo.com/{i}") for i in range(20)]
    dedup = Deduplicator()
    result = dedup.deduplicate(articles)
    assert len(result) <= 20
