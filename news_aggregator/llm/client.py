from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from news_aggregator.llm.prompts import build_prompt
from news_aggregator.models.article import Article


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate_headline_and_summary(
        self,
        articles: list[Article],
        headline_max_chars: int,
        summary_max_lines: int,
    ) -> tuple[str, str]:
        """Return (headline, summary) for the given articles."""
        if not articles:
            raise LLMError("Cannot generate headline/summary: no articles provided")

        messages = build_prompt(articles, headline_max_chars, summary_max_lines)

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise LLMError(f"LLM API call failed: {e}") from e

        raw_content = response.choices[0].message.content or ""
        return self._parse_response(raw_content, headline_max_chars)

    def _parse_response(self, content: str, headline_max_chars: int) -> tuple[str, str]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM returned invalid JSON: {content[:200]}") from e

        headline = data.get("headline", "").strip()
        summary = data.get("summary", "").strip()

        if not headline:
            raise LLMError("LLM response missing 'headline' field")
        if not summary:
            raise LLMError("LLM response missing 'summary' field")

        headline = _truncate_headline(headline, headline_max_chars)
        return headline, summary

    async def check_connectivity(self) -> bool:
        """Lightweight test — returns True if the LLM endpoint is reachable."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


def _truncate_headline(headline: str, max_chars: int) -> str:
    """Truncate at the last word boundary before max_chars, appending '...'."""
    if len(headline) <= max_chars:
        return headline
    # Allow room for the ellipsis
    truncated = headline[: max_chars - 3]
    # Cut back to the last word boundary
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."
