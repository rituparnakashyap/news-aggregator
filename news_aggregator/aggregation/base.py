from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from news_aggregator.models.article import Article


class StrategyError(Exception):
    pass


class BaseStrategy(ABC):
    name: ClassVar[str]
    default_output_template: ClassVar[str]  # Jinja2 template string; subclasses must define this

    @abstractmethod
    def select(self, articles: list[Article], params: dict[str, Any]) -> list[Article]:
        """Given a deduplicated+ranked list, return the final selection."""
        ...
