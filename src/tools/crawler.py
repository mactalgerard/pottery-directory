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

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

# Crawled content is truncated to this many characters before being passed to
# Claude. Homepage content above ~12 000 chars is rarely useful for field
# extraction and keeping it short is the biggest lever on token costs.
MAX_CONTENT_CHARS = 12_000


async def crawl_website(url: str, timeout: int = 30) -> Optional[str]:
    """
    Crawl a single URL using Crawl4AI and return cleaned markdown content.

    Uses fit_markdown (Crawl4AI's filtered output) which strips navigation,
    footers, cookie banners, and boilerplate. Content is truncated to
    MAX_CONTENT_CHARS before returning.

    Args:
        url:     The full URL to crawl (must include https://).
        timeout: Maximum seconds to wait for the page to load. Default 30.

    Returns:
        Cleaned markdown string (truncated), or None if the crawl fails
        (network error, timeout, robots.txt block, too little content, etc.).
    """
    try:
        config = CrawlerRunConfig(page_timeout=timeout * 1000)
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url, config=config)
            r = result[0]

            if not r.success:
                logger.warning("Crawl failed for %s: %s", url, getattr(r, "error_message", "unknown"))
                return None

            content = r.markdown.fit_markdown or str(r.markdown)

            if len(content.strip()) < 100:
                logger.warning("Crawl returned too little content for %s (%d chars)", url, len(content))
                return None

            return content[:MAX_CONTENT_CHARS]

    except Exception as exc:
        logger.warning("Crawl exception for %s: %s", url, exc)
        return None


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
    sem = asyncio.Semaphore(concurrency)

    async def _crawl_with_sem(url: str) -> tuple[str, Optional[str]]:
        async with sem:
            try:
                content = await asyncio.wait_for(
                    crawl_website(url, timeout=timeout),
                    timeout=timeout + 10,  # hard outer timeout, slightly above Playwright's
                )
            except asyncio.TimeoutError:
                logger.warning("Hard timeout exceeded for %s", url)
                content = None
            return url, content

    pairs = await asyncio.gather(*[_crawl_with_sem(u) for u in urls])
    return dict(pairs)
