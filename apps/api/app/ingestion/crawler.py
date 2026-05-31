"""Async HTTP crawler for bdlaws.minlaw.gov.bd.

Fetches Act pages with polite rate limiting, ETag/Last-Modified conditional
requests, and bounded exponential backoff that honours ``Retry-After``. The
original HTML is preserved alongside metadata so the parser can inspect the
source document independently of our normalised representation (FR-IN-7).

Author: Al Amin Ahamed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_BACKOFF_SECONDS = 120.0


class BdlawsFetchError(Exception):
    """Raised on an unrecoverable bdlaws fetch failure after retries."""


@dataclass(frozen=True)
class CrawlResult:
    """The outcome of one bdlaws page fetch.

    Attributes:
        url: The URL that was requested.
        html: The full page HTML; empty string when ``not_modified`` is True.
        language: The language variant fetched (``bn`` or ``en``).
        act_slug: The Act slug from configuration.
        fetched_at: UTC timestamp of the successful response.
        etag: ETag from the response, or ``None`` if the server did not send one.
        last_modified: Last-Modified value from the response, or ``None``.
        not_modified: True when the server returned 304 — content is unchanged.
    """

    url: str
    html: str
    language: str
    act_slug: str
    fetched_at: datetime
    etag: str | None
    last_modified: str | None
    not_modified: bool


def build_client(settings: Settings) -> httpx.AsyncClient:
    """Construct an async HTTP client configured for bdlaws crawling.

    Args:
        settings: Application settings supplying timeout and User-Agent.

    Returns:
        httpx.AsyncClient: Client with User-Agent, timeout, and redirect following.
    """
    return httpx.AsyncClient(
        headers={"User-Agent": settings.http_user_agent},
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
    )


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Compute the backoff delay for a retryable response.

    Honours an explicit ``Retry-After`` header (seconds integer) if present;
    otherwise uses capped exponential backoff.

    Args:
        response: The response that triggered the retry.
        attempt: Zero-based attempt number that just failed.

    Returns:
        float: Seconds to wait before the next attempt.
    """
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return min(float(retry_after), _MAX_BACKOFF_SECONDS)
    return min(2.0**attempt, _MAX_BACKOFF_SECONDS)


async def fetch_act_page(
    url: str,
    act_slug: str,
    language: str,
    *,
    etags: dict[str, str] | None = None,
    last_modified_store: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
    settings: Settings | None = None,
) -> CrawlResult:
    """Fetch one bdlaws Act page with conditional-request and retry support.

    Sends ``If-None-Match`` / ``If-Modified-Since`` headers when prior values are
    available, returning a ``not_modified=True`` result for 304 responses so the
    ingestion task can skip re-processing (FR-IN-4). The polite rate-limit delay
    is applied before the first attempt so concurrent calls do not burst.

    Args:
        url: Absolute URL of the bdlaws page to fetch.
        act_slug: Act slug carried through to the result for logging.
        language: Language variant (``bn`` or ``en``).
        etags: Mutable ETag store keyed by URL; updated on each 200 response.
        last_modified_store: Mutable Last-Modified store; updated on each 200.
        client: Optional pre-built client; a fresh one is created if absent.
        settings: Application settings; resolved from configuration if absent.

    Returns:
        CrawlResult: The fetch outcome, including preserved HTML or not_modified.

    Raises:
        BdlawsFetchError: On a non-retryable HTTP error or after exhausting retries.
    """
    settings = settings or get_settings()
    owns_client = client is None
    if client is None:
        client = build_client(settings)

    # Polite delay between portal requests.
    delay = 1.0 / max(settings.bdlaws_rate_limit_rps, 0.01)
    await asyncio.sleep(delay)

    headers: dict[str, str] = {}
    if etags is not None and url in etags:
        headers["If-None-Match"] = etags[url]
    if last_modified_store is not None and url in last_modified_store:
        headers["If-Modified-Since"] = last_modified_store[url]

    last_status = 0
    try:
        for attempt in range(settings.http_max_retries + 1):
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                raise BdlawsFetchError(f"GET {url} failed: {exc}") from exc

            last_status = response.status_code

            if response.status_code == 304:
                logger.debug(
                    "bdlaws page not modified",
                    extra={"url": url, "act_slug": act_slug, "language": language},
                )
                return CrawlResult(
                    url=url,
                    html="",
                    language=language,
                    act_slug=act_slug,
                    fetched_at=datetime.now(UTC),
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    not_modified=True,
                )

            if response.status_code in _RETRYABLE_STATUS:
                if attempt >= settings.http_max_retries:
                    break
                delay_s = _retry_after_seconds(response, attempt)
                logger.warning(
                    "retrying bdlaws fetch after transient failure",
                    extra={
                        "url": url,
                        "status": response.status_code,
                        "attempt": attempt,
                        "delay_s": delay_s,
                    },
                )
                await asyncio.sleep(delay_s)
                continue

            if response.status_code != 200:
                raise BdlawsFetchError(f"GET {url} returned {response.status_code} (non-retryable)")

            # Successful 200: update conditional-request stores and return.
            if etags is not None and "ETag" in response.headers:
                etags[url] = response.headers["ETag"]
            if last_modified_store is not None and "Last-Modified" in response.headers:
                last_modified_store[url] = response.headers["Last-Modified"]

            logger.info(
                "fetched bdlaws page",
                extra={
                    "url": url,
                    "act_slug": act_slug,
                    "language": language,
                    "bytes": len(response.content),
                },
            )
            return CrawlResult(
                url=url,
                html=response.text,
                language=language,
                act_slug=act_slug,
                fetched_at=datetime.now(UTC),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                not_modified=False,
            )

        raise BdlawsFetchError(
            f"GET {url} failed after {settings.http_max_retries} retries "
            f"(last status {last_status})"
        )
    finally:
        if owns_client:
            await client.aclose()
