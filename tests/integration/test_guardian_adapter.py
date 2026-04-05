from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from pytest_httpx import HTTPXMock

from news_aggregator.config.schema import SourceConfig
from news_aggregator.sources.guardian import GuardianSource
from news_aggregator.sources.base import SourceError
import news_aggregator.sources  # noqa: F401 — trigger registration


MOCK_RESPONSE = {
    "response": {
        "status": "ok",
        "total": 2,
        "results": [
            {
                "id": "technology/2024/jun/01/ai-news",
                "webTitle": "Major AI Development Announced",
                "webUrl": "https://theguardian.com/technology/ai-news",
                "webPublicationDate": "2024-06-01T10:00:00Z",
                "fields": {
                    "trailText": "A significant AI development was announced today.",
                    "bodyText": "Scientists at a leading institution announced...",
                },
            },
            {
                "id": "technology/2024/jun/01/chip",
                "webTitle": "New Semiconductor Breakthrough",
                "webUrl": "https://theguardian.com/technology/chip",
                "webPublicationDate": "2024-06-01T08:00:00Z",
                "fields": {},
            },
        ],
    }
}


@pytest.fixture
def source_config():
    return SourceConfig(name="guardian")


@pytest.mark.asyncio
async def test_fetch_returns_articles(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert len(articles) == 2
    assert articles[0].title == "Major AI Development Announced"
    assert articles[0].url == "https://theguardian.com/technology/ai-news"
    assert articles[0].category == "technology"
    assert articles[0].source.adapter_name == "guardian"
    assert articles[0].source.source_id == "the-guardian"
    assert articles[0].description == "A significant AI development was announced today."


@pytest.mark.asyncio
async def test_fetch_published_at(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles[0].published_at == datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fetch_empty_results(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"response": {"status": "ok", "results": []}})

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles == []


@pytest.mark.asyncio
async def test_fetch_server_error_raises(httpx_mock: HTTPXMock, source_config):
    for _ in range(3):
        httpx_mock.add_response(status_code=503)

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(SourceError):
                await source.fetch("technology", lookback_hours=24)


@pytest.mark.asyncio
async def test_fetch_rate_limit_raises(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(status_code=429)

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        from news_aggregator.sources.base import RateLimitError
        with pytest.raises(RateLimitError):
            await source.fetch("technology", lookback_hours=24)


@pytest.mark.asyncio
async def test_category_finance_maps_to_business(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"response": {"status": "ok", "results": []}})

    async with httpx.AsyncClient() as client:
        source = GuardianSource(api_key="test-key", config=source_config, client=client)
        await source.fetch("finance", lookback_hours=24)

    # Check that the section param was "business"
    request = httpx_mock.get_requests()[0]
    assert "section=business" in str(request.url)


def test_missing_api_key_raises(source_config):
    with pytest.raises(SourceError, match="GUARDIAN_KEY is required"):
        GuardianSource(api_key=None, config=source_config)
