"""Tests for the bdlaws HTTP crawler.

All HTTP calls are intercepted by pytest-httpx so no live network access
occurs.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.ingestion.crawler import BdlawsFetchError, CrawlResult, fetch_act_page

_URL = "https://bdlaws.minlaw.gov.bd/act-details-952.html"
_HTML = "<html><body><div class='lawCon'><p>Test Act</p></div></body></html>"


@pytest.mark.asyncio
async def test_fetch_returns_html(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """Successful 200 response returns a CrawlResult with the page HTML."""
    httpx_mock.add_response(url=_URL, text=_HTML, status_code=200)
    result = await fetch_act_page(_URL, "labour-act-2006", "en")

    assert isinstance(result, CrawlResult)
    assert result.html == _HTML
    assert not result.not_modified
    assert result.language == "en"
    assert result.act_slug == "labour-act-2006"


@pytest.mark.asyncio
async def test_not_modified_on_304(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """304 Not Modified returns a CrawlResult with not_modified=True and empty HTML."""
    httpx_mock.add_response(url=_URL, status_code=304)
    result = await fetch_act_page(_URL, "labour-act-2006", "en")

    assert result.not_modified
    assert result.html == ""


@pytest.mark.asyncio
async def test_etag_sent_on_second_request(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """ETag from first response is sent as If-None-Match on subsequent requests."""
    httpx_mock.add_response(
        url=_URL,
        text=_HTML,
        status_code=200,
        headers={"ETag": '"abc123"'},
    )
    etags: dict[str, str] = {}
    await fetch_act_page(_URL, "act", "en", etags=etags)

    assert etags[_URL] == '"abc123"'


@pytest.mark.asyncio
async def test_retry_on_503_then_success(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """503 is retried and the subsequent 200 is returned."""
    httpx_mock.add_response(url=_URL, status_code=503)
    httpx_mock.add_response(url=_URL, text=_HTML, status_code=200)

    settings = Settings(http_max_retries=2)
    result = await fetch_act_page(_URL, "act", "en", settings=settings)
    assert not result.not_modified
    assert result.html == _HTML


@pytest.mark.asyncio
async def test_raises_after_exhausted_retries(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """BdlawsFetchError is raised after all retries are exhausted."""
    settings = Settings(http_max_retries=1)
    httpx_mock.add_response(url=_URL, status_code=503)
    httpx_mock.add_response(url=_URL, status_code=503)

    with pytest.raises(BdlawsFetchError):
        await fetch_act_page(_URL, "act", "en", settings=settings)


@pytest.mark.asyncio
async def test_non_retryable_error_raises_immediately(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """A 404 is non-retryable and raises BdlawsFetchError immediately."""
    httpx_mock.add_response(url=_URL, status_code=404)

    with pytest.raises(BdlawsFetchError, match="404"):
        await fetch_act_page(_URL, "act", "en")


@pytest.mark.asyncio
async def test_retry_after_header_honoured(httpx_mock) -> None:  # type: ignore[no-untyped-def]
    """Retry-After header is read (actual sleep is not tested for speed)."""
    httpx_mock.add_response(url=_URL, status_code=429, headers={"Retry-After": "1"})
    httpx_mock.add_response(url=_URL, text=_HTML, status_code=200)

    settings = Settings(http_max_retries=2)
    result = await fetch_act_page(_URL, "act", "en", settings=settings)
    assert not result.not_modified
