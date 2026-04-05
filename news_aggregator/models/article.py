from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArticleSource:
    adapter_name: str   # "newsapi" | "guardian" | "gdelt"
    source_id: str      # source-specific name/ID
    url: str


@dataclass
class Article:
    title: str
    url: str
    published_at: datetime
    category: str
    source: ArticleSource
    id: str = field(default="")
    description: str | None = None
    content_snippet: str | None = None  # up to ~500 chars for LLM context
    mention_count: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _make_id(self.title, self.url)


def _make_id(title: str, url: str) -> str:
    """Stable 16-char ID derived from title and URL."""
    key = (title.lower().strip() + url.strip()).encode()
    return hashlib.sha256(key).hexdigest()[:16]
