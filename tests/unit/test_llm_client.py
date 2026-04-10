from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_aggregator.llm.client import LLMClient, LLMError, _truncate_headline
from news_aggregator.llm.prompts import build_prompt
from news_aggregator.models.article import Article, ArticleSource


def _article(title: str = "Test Article", n: int = 0) -> Article:
    return Article(
        title=title,
        url=f"https://foo.com/{n}",
        published_at=datetime.now(timezone.utc),
        category="technology",
        source=ArticleSource(adapter_name="newsapi", source_id="src", url="https://x.com"),
        description="A short description of the article.",
        content_snippet="The full snippet of the article content.",
    )


def _make_client() -> LLMClient:
    return LLMClient(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )


def _mock_completion(headline: str, summaries: list[str]) -> MagicMock:
    content = json.dumps({"headline": headline, "summaries": summaries})
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


# ---------------------------------------------------------------------------
# _truncate_headline
# ---------------------------------------------------------------------------

def test_truncate_no_op_when_short():
    assert _truncate_headline("Short headline", 100) == "Short headline"


def test_truncate_exactly_at_limit():
    s = "a" * 100
    assert _truncate_headline(s, 100) == s


def test_truncate_over_limit_at_word_boundary():
    headline = "This is a very long headline that exceeds the character limit"
    result = _truncate_headline(headline, 30)
    assert len(result) <= 30
    assert result.endswith("...")


def test_truncate_preserves_word_boundary():
    headline = "Breaking News from the Technology World Today"
    result = _truncate_headline(headline, 25)
    assert not result[:-3].endswith(" ")  # no trailing space before ellipsis
    assert result.endswith("...")


def test_truncate_single_very_long_word():
    headline = "Supercalifragilisticexpialidocious"
    result = _truncate_headline(headline, 10)
    assert result.endswith("...")
    assert len(result) <= 10


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_structure():
    articles = [_article(f"Article {i}", i) for i in range(3)]
    messages = build_prompt(articles, headline_max_chars=100, summary_max_lines=3)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_prompt_mentions_limits():
    articles = [_article()]
    messages = build_prompt(articles, headline_max_chars=80, summary_max_lines=2)
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "80" in system
    assert "2" in system
    assert "80" in user or "2" in user


def test_build_prompt_caps_at_five_articles():
    articles = [_article(f"Article {i}", i) for i in range(10)]
    messages = build_prompt(articles, headline_max_chars=100, summary_max_lines=3)
    user = messages[1]["content"]
    # Only first 5 numbered items should appear
    assert "5." in user
    assert "6." not in user


def test_build_prompt_uses_content_snippet():
    article = _article()
    article.content_snippet = "The snippet content."
    messages = build_prompt([article], headline_max_chars=100, summary_max_lines=3)
    assert "The snippet content." in messages[1]["content"]


def test_build_prompt_falls_back_to_description():
    article = _article()
    article.content_snippet = None
    article.description = "The description."
    messages = build_prompt([article], headline_max_chars=100, summary_max_lines=3)
    assert "The description." in messages[1]["content"]


def test_build_prompt_falls_back_to_title():
    article = _article(title="Just the title")
    article.content_snippet = None
    article.description = None
    messages = build_prompt([article], headline_max_chars=100, summary_max_lines=3)
    assert "Just the title" in messages[1]["content"]


# ---------------------------------------------------------------------------
# LLMClient.generate_headline_and_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_returns_headline_and_summary():
    client = _make_client()
    mock_resp = _mock_completion("Tech News Today", ["Line one.", "Line two.", "Line three."])

    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        headline, summaries = await client.generate_headline_and_summary(
            [_article()], headline_max_chars=100, summary_max_lines=3
        )

    assert headline == "Tech News Today"
    assert summaries == ["Line one.", "Line two.", "Line three."]


@pytest.mark.asyncio
async def test_generate_truncates_long_headline():
    client = _make_client()
    long_headline = "This is a very long headline that definitely exceeds the character limit set for this test"
    mock_resp = _mock_completion(long_headline, ["Summary line."])

    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        headline, _ = await client.generate_headline_and_summary(
            [_article()], headline_max_chars=30, summary_max_lines=1
        )

    assert len(headline) <= 30
    assert headline.endswith("...")


@pytest.mark.asyncio
async def test_generate_raises_on_invalid_json():
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "not json at all"

    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(LLMError, match="invalid JSON"):
            await client.generate_headline_and_summary(
                [_article()], headline_max_chars=100, summary_max_lines=3
            )


@pytest.mark.asyncio
async def test_generate_raises_on_missing_headline():
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps({"summaries": ["A summary."]})

    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(LLMError, match="missing 'headline'"):
            await client.generate_headline_and_summary(
                [_article()], headline_max_chars=100, summary_max_lines=3
            )


@pytest.mark.asyncio
async def test_generate_raises_on_missing_summaries():
    client = _make_client()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps({"headline": "A headline."})

    with patch.object(client._client.chat.completions, "create", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(LLMError, match="missing 'summaries'"):
            await client.generate_headline_and_summary(
                [_article()], headline_max_chars=100, summary_max_lines=3
            )


@pytest.mark.asyncio
async def test_generate_raises_on_empty_articles():
    client = _make_client()
    with pytest.raises(LLMError, match="no articles"):
        await client.generate_headline_and_summary(
            [], headline_max_chars=100, summary_max_lines=3
        )


@pytest.mark.asyncio
async def test_generate_raises_on_api_failure():
    client = _make_client()

    with patch.object(
        client._client.chat.completions,
        "create",
        new=AsyncMock(side_effect=Exception("connection refused")),
    ):
        with pytest.raises(LLMError, match="LLM API call failed"):
            await client.generate_headline_and_summary(
                [_article()], headline_max_chars=100, summary_max_lines=3
            )
