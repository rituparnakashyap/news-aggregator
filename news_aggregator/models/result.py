from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from news_aggregator.models.article import Article


@dataclass
class CategoryResult:
    category: str
    articles: list[Article]
    headline: str
    summary: str


@dataclass
class AggregatedResult:
    generated_at: datetime
    lookback_hours: int
    categories: list[CategoryResult]
