from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from pytest_httpx import HTTPXMock

from news_aggregator.config.schema import SourceConfig
from news_aggregator.sources.gdelt import GdeltSource
from news_aggregator.sources.base import SourceError
import news_aggregator.sources  # noqa: F401 — trigger registration


MOCK_RESPONSE = {
    "articles": [
        {
            "url": "https://reuters.com/tech/ai-advance",
            "title": "AI Researchers Announce Major Advance",
            "seendate": "20240601T100000Z",
            "domain": "reuters.com",
            "language": "English",
            "sourcecountry": "United States",
        },
        {
            "url": "https://bloomberg.com/tech/chips",
            "title": "Chip Shortage Eases as New Fabs Open",
            "seendate": "20240601T080000Z",
            "domain": "bloomberg.com",
            "language": "English",
            "sourcecountry": "United States",
        },
    ]
}


@pytest.fixture
def source_config():
    return SourceConfig(name="gdelt")


@pytest.mark.asyncio
async def test_fetch_returns_articles(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = GdeltSource(api_key=None, config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert len(articles) == 2
    assert articles[0].title == "AI Researchers Announce Major Advance"
    assert articles[0].url == "https://reuters.com/tech/ai-advance"
    assert articles[0].category == "technology"
    assert articles[0].source.adapter_name == "gdelt"
    assert articles[0].source.source_id == "reuters.com"


@pytest.mark.asyncio
async def test_fetch_published_at_parsed(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json=MOCK_RESPONSE)

    async with httpx.AsyncClient() as client:
        source = GdeltSource(api_key=None, config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles[0].published_at == datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fetch_empty_response(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"articles": []})

    async with httpx.AsyncClient() as client:
        source = GdeltSource(api_key=None, config=source_config, client=client)
        articles = await source.fetch("technology", lookback_hours=24)

    assert articles == []


@pytest.mark.asyncio
async def test_fetch_server_error_raises(httpx_mock: HTTPXMock, source_config):
    for _ in range(3):
        httpx_mock.add_response(status_code=500)

    async with httpx.AsyncClient() as client:
        source = GdeltSource(api_key=None, config=source_config, client=client)
        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(SourceError):
                await source.fetch("technology", lookback_hours=24)


@pytest.mark.asyncio
async def test_no_api_key_required(source_config):
    # GDELT should instantiate fine with no key
    source = GdeltSource(api_key=None, config=source_config)
    assert source.api_key is None


@pytest.mark.asyncio
async def test_finance_category_query(httpx_mock: HTTPXMock, source_config):
    httpx_mock.add_response(json={"articles": []})

    async with httpx.AsyncClient() as client:
        source = GdeltSource(api_key=None, config=source_config, client=client)
        await source.fetch("finance", lookback_hours=24)

    request = httpx_mock.get_requests()[0]
    assert "finance" in str(request.url).lower() or "economy" in str(request.url).lower()
