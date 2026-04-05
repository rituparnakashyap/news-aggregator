from __future__ import annotations

import random
from typing import Any

from news_aggregator.aggregation.base import BaseStrategy, StrategyError
from news_aggregator.aggregation.registry import register
from news_aggregator.models.article import Article


@register
class TopNLuckyMStrategy(BaseStrategy):
    name = "TopNLuckyM"

    def select(self, articles: list[Article], params: dict[str, Any]) -> list[Article]:
        if "n" not in params:
            raise StrategyError("TopNLuckyM strategy requires 'n' in params")
        if "m" not in params:
            raise StrategyError("TopNLuckyM strategy requires 'm' in params")

        n = int(params["n"])
        m = int(params["m"])

        if n < 1:
            raise StrategyError("TopNLuckyM 'n' must be >= 1")
        if m < 0:
            raise StrategyError("TopNLuckyM 'm' must be >= 0")
        if m >= n:
            raise StrategyError("TopNLuckyM 'm' must be < 'n'")

        top_pool = articles[:n]
        lower_pool = articles[n:]

        lucky_count = min(m, len(lower_pool))
        lucky = random.sample(lower_pool, lucky_count) if lucky_count > 0 else []

        # Keep (n - lucky_count) deterministic top articles, fill rest with lucky picks
        deterministic = top_pool[: n - lucky_count]
        result = deterministic + lucky

        return result
