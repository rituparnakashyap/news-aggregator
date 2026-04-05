from __future__ import annotations

from datetime import datetime, timezone

import pytest
import httpx
from pytest_httpx import HTTPXMock

from news_aggregator.config.schema import SourceConfig
from news_aggregator.sources.newsapi import NewsApiSource
from news_aggregator.sources.base import SourceError
from news_aggregator.sources.registry import get_source
import news_aggregator.sources  # noqa: F401 — trigger registration


MOCK_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"id": "bbc-news", "name": "BBC News"},
            "title": "AI Breakthrough in 2024",
            "description": "A major AI advancement was announced.",
            "url": "https://bbc.com/news/ai-breakthrough",
            "publishedAt": "2024-06-01T10:00:00Z",
            "content": "Scientists have developed a new AI model...",
        },
        {
            "source": {"id": None, "name": "TechCrunch"},
            "title": "New Chip Architecture Unveiled",
            "description": "A next-gen chip was unveiled today.",
            "url": "https://techcrunch.com/chip-architecture",
            "publishedAt": "2024-06-01T08:00:00Z",
            "content": None,
        },
    ],
}


@pytest.fixture
def source_config():
    return SourceConfig(name="newsapi")


@pytest.mark.asyncio
async def test_fetch_returns_articles(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert len(articles) == 2
    assert articles[0].title == "AI Breakthrough in 2024"
    assert articles[0].url == "https://bbc.com/news/ai-breakthrough"
    assert articles[0].category == "technology"
    assert articles[0].source.adapter_name == "newsapi"
    assert articles[0].source.source_id == "BBC News"
    assert articles[0].description == "A major AI advancement was announced."
    assert articles[0].content_snippet is not None


@pytest.mark.asyncio
async def test_fetch_sets_published_at(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles[0].published_at == datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fetch_filters_removed_articles(httpx_mock: HTTPXMock, source_config):
    response = {
        "status": "ok",
        "articles": [
            {
                "source": {"name": "Removed"},
                "title": "[Removed]",
                "url": "https://removed.com",
                "publishedAt": "2024-06-01T10:00:00Z",
            }
        ],
    }
    httpx_mock.add_response(json=response)

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles == []


@pytest.mark.asyncio
async def test_fetch_empty_response(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"status": "ok", "articles": []})

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles == []


@pytest.mark.asyncio
async def test_fetch_api_error_raises(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"status": "error", "message": "Invalid API key"})

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="bad-key", config=source_config, client=client)
        with pytest.raises(SourceError, match="Invalid API key"):
            await source.fetch("technology", lookback_hours=24)


@pytest.mark.asyncio
async def test_fetch_http_500_raises(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(status_code=500)

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        with pytest.raises(SourceError, match="Server error 500"):
            await source.fetch("technology", lookback_hours=24)


@pytest.mark.asyncio
async def test_fetch_rate_limit_raises(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(status_code=429)

    async with httpx.AsyncClient() as client:
        source = NewsApiSource(api_key="test-key", config=source_config, client=client)
        from news_aggregator.sources.base import RateLimitError
        with pytest.raises(RateLimitError):
            await source.fetch("technology", lookback_hours=24)


def test_missing_api_key_raises(source_config):
    with pytest.raises(SourceError, match="NEWSAPI_KEY is required"):
        NewsApiSource(api_key=None, config=source_config)


def test_get_source_factory_returns_newsapi(source_config):
    src = get_source("newsapi", api_key="key", config=source_config)
    assert isinstance(src, NewsApiSource)


def test_get_source_unknown_raises(source_config):
    with pytest.raises(ValueError, match="Unknown news source"):
        get_source("nonexistent", api_key=None, config=source_config)
