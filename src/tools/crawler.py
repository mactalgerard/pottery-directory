"""
Crawl4AI wrapper for all website crawling in the pottery-directory pipeline.

Rules:
  - Agents must never call Crawl4AI directly. All crawling goes through this module.
  - On crawl failure, log the error and return None so callers can gracefully
    degrade to null enrichment fields rather than crashing the pipeline.
  - All functions are async — use asyncio when calling from pipeline.py.
"""

import asyncio
import logging
from typing import Optional

from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


async def crawl_website(url: str, timeout: int = 30) -> Optional[str]:
    """
    Crawl a single URL using Crawl4AI and return cleaned markdown content.

    Strips navigation, footers, cookie banners, and boilerplate so that
    the returned text is suitable for passing directly to a Claude prompt.

    Args:
        url:     The full URL to crawl (must include https://).
        timeout: Maximum seconds to wait for the page to load. Default 30.

    Returns:
        Cleaned markdown string of the page content, or None if the crawl
        fails (network error, timeout, robots.txt block, etc.).
    """
    # TODO: Initialise AsyncWebCrawler from crawl4ai
    # TODO: Run crawler.arun(url=url) with appropriate CrawlerRunConfig
    # TODO: Extract result.markdown_v2.raw_markdown (or equivalent)
    # TODO: Strip content below a minimum length threshold (e.g. < 100 chars → None)
    # TODO: Log warning on failure; do not raise — return None
    raise NotImplementedError


async def crawl_many(
    urls: list[str],
    concurrency: int = 5,
    timeout: int = 30,
) -> dict[str, Optional[str]]:
    """
    Crawl multiple URLs concurrently, up to `concurrency` at a time.

    Uses an asyncio.Semaphore to cap concurrent requests and avoid
    overwhelming both the target servers and the local event loop.

    Args:
        urls:        List of URLs to crawl.
        concurrency: Maximum simultaneous crawls. Default 5.
        timeout:     Per-URL timeout in seconds. Default 30.

    Returns:
        Dict mapping each input URL to its cleaned markdown string (or None
        if the crawl failed for that URL).
    """
    # TODO: Create asyncio.Semaphore(concurrency)
    # TODO: Define a _crawl_with_semaphore(url) helper that acquires the semaphore
    # TODO: asyncio.gather all URLs using _crawl_with_semaphore
    # TODO: Return {url: result} dict
    raise NotImplementedError
