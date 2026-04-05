from __future__ import annotations

import re

from news_aggregator.models.article import Article

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "that", "this", "it", "its", "as", "up", "into",
    "not", "no", "than", "over", "after", "new", "says", "say", "said",
})

_NON_ALPHA = re.compile(r"[^a-z0-9\s]")


def _tokenize(text: str) -> frozenset[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    cleaned = _NON_ALPHA.sub(" ", text.lower())
    return frozenset(w for w in cleaned.split() if w and w not in _STOPWORDS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class Deduplicator:
    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        """
        Deduplicate articles:
        1. Exact dedup by Article.id
        2. Fuzzy dedup by Jaccard token similarity on titles

        Merged articles accumulate mention_count. Result is sorted by
        mention_count DESC, then published_at DESC.
        """
        # Pass 1: exact dedup by id
        seen_ids: dict[str, Article] = {}
        for article in articles:
            if article.id in seen_ids:
                existing = seen_ids[article.id]
                existing.mention_count += article.mention_count
                if article.published_at < existing.published_at:
                    existing.published_at = article.published_at
                if not existing.description and article.description:
                    existing.description = article.description
            else:
                seen_ids[article.id] = article

        unique = list(seen_ids.values())

        # Pass 2: fuzzy dedup by title similarity
        token_sets = [_tokenize(a.title) for a in unique]
        merged = [False] * len(unique)
        clusters: list[Article] = []

        for i, article in enumerate(unique):
            if merged[i]:
                continue
            # This article is the "canonical" for its cluster
            for j in range(i + 1, len(unique)):
                if merged[j]:
                    continue
                similarity = _jaccard(token_sets[i], token_sets[j])
                if similarity >= self.threshold:
                    # Merge j into i
                    article.mention_count += unique[j].mention_count
                    if unique[j].published_at < article.published_at:
                        article.published_at = unique[j].published_at
                    if not article.description and unique[j].description:
                        article.description = unique[j].description
                    merged[j] = True
            clusters.append(article)

        clusters.sort(key=lambda a: (-a.mention_count, -a.published_at.timestamp()))
        return clusters
