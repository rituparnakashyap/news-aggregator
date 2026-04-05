from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from news_aggregator.aggregation.deduplicator import Deduplicator
from news_aggregator.aggregation.registry import get_strategy
from news_aggregator.config.schema import AppConfig, CategoryConfig
from news_aggregator.llm.client import LLMClient
from news_aggregator.models.article import Article
from news_aggregator.models.result import AggregatedResult, CategoryResult
from news_aggregator.sources.base import SourceError
from news_aggregator.sources.registry import get_source

import news_aggregator.aggregation  # noqa: F401 — register strategies
import news_aggregator.sources  # noqa: F401 — register source adapters

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: AppConfig, env: dict[str, str]) -> None:
        self.config = config
        self.env = env
        self.llm = LLMClient(
            api_key=env.get("LLM_API_KEY", ""),
            base_url=env.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=config.llm.model,
            temperature=config.llm.temperature,
        )

    async def run(self) -> AggregatedResult:
        async with httpx.AsyncClient() as http_client:
            tasks = [
                self._run_category(cat_cfg, http_client)
                for cat_cfg in self.config.categories
            ]
            category_results = await asyncio.gather(*tasks)

        return AggregatedResult(
            generated_at=datetime.now(timezone.utc),
            lookback_hours=self.config.aggregation.lookback_hours,
            categories=[r for r in category_results if r is not None],
        )

    async def _run_category(
        self,
        cat_cfg: CategoryConfig,
        http_client: httpx.AsyncClient,
    ) -> CategoryResult | None:
        category = cat_cfg.name

        # Determine which sources to use
        enabled_source_names = {
            s.name for s in self.config.sources if s.enabled
        }
        source_names = cat_cfg.sources or list(enabled_source_names)
        source_configs = {s.name: s for s in self.config.sources}

        lookback = self.config.aggregation.lookback_hours

        # Fetch from all sources concurrently; degrade gracefully on failure
        fetch_tasks = []
        for src_name in source_names:
            if src_name not in enabled_source_names:
                continue
            src_cfg = source_configs.get(src_name)
            if not src_cfg:
                continue
            api_key = self.env.get(f"{src_name.upper()}_KEY")
            try:
                source = get_source(src_name, api_key=api_key, config=src_cfg, client=http_client)
                fetch_tasks.append(source.fetch(category, lookback_hours=lookback))
            except Exception as e:
                logger.warning("[%s] Failed to init source '%s': %s", category, src_name, e)

        if not fetch_tasks:
            logger.warning("[%s] No sources available, skipping category", category)
            return None

        raw_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        articles: list[Article] = []
        for src_name, result in zip(source_names, raw_results):
            if isinstance(result, Exception):
                logger.warning("[%s] Source '%s' failed: %s", category, src_name, result)
            else:
                articles.extend(result)

        if not articles:
            logger.warning("[%s] No articles fetched from any source", category)
            return CategoryResult(
                category=category,
                articles=[],
                headline=f"No news available for {category}",
                summary="No articles were fetched for this category.",
            )

        # Deduplicate
        dedup = Deduplicator(threshold=self.config.aggregation.dedup_threshold)
        articles = dedup.deduplicate(articles)

        # Apply strategy
        strategy_name = cat_cfg.strategy or self.config.aggregation.strategy
        strategy_params = cat_cfg.strategy_params or self.config.aggregation.params
        strategy_cls = get_strategy(strategy_name)
        selected = strategy_cls().select(articles, strategy_params)

        # Generate headline + summary via LLM
        headline, summary = await self.llm.generate_headline_and_summary(
            selected,
            headline_max_chars=self.config.llm.headline_max_chars,
            summary_max_lines=self.config.llm.summary_max_lines,
        )

        return CategoryResult(
            category=category,
            articles=selected,
            headline=headline,
            summary=summary,
        )
