from __future__ import annotations

from typing import Any, ClassVar

from news_aggregator.aggregation.base import BaseStrategy, StrategyError
from news_aggregator.aggregation.registry import register
from news_aggregator.models.article import Article


@register
class TopNStrategy(BaseStrategy):
    name = "TopN"
    default_output_template: ClassVar[str] = (
        "{{ headline }}\n"
        "{% for s in summaries %}"
        "{{ loop.index }}. {{ s }}\n"
        "{% endfor %}"
    )

    def select(self, articles: list[Article], params: dict[str, Any]) -> list[Article]:
        if "n" not in params:
            raise StrategyError("TopN strategy requires 'n' in params")
        n = int(params["n"])
        if n < 1:
            raise StrategyError("TopN 'n' must be >= 1")
        return articles[:n]
