"""
EnrichmentAgent — enriches each CleanListing with niche-specific fields.

Takes CleanListing objects and the country-specific enrichment field definitions
from context/enrichment_fields_{COUNTRY}.md. Crawls business websites via
Crawl4AI and uses Claude (tool_use) to extract structured pottery fields.

Concurrency: up to 5 listings are enriched in parallel via asyncio.

Output: list of EnrichedListing objects.
Writes to: data/enriched/{COUNTRY}/enriched_{date}.csv

Tools available (via Claude tool_use):
  crawl_website(url: str) -> str   — returns cleaned markdown of a page
  web_search(query: str) -> str    — fallback if no website or website is thin
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import anthropic
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

from src.models import CleanListing, CountryCode, EnrichedListing
from src.tools import crawler

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

ENRICHED_DIR = Path("data/enriched")
CONTEXT_DIR = Path("context")
MODEL = "claude-sonnet-4-20250514"
CONCURRENCY = 5

TOOLS: list[dict] = [
    {
        "name": "crawl_website",
        "description": (
            "Crawl a business website and return cleaned markdown content. "
            "Use this to extract enrichment fields from the studio's own site. "
            "Returns an empty string if the crawl fails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to crawl, including https://.",
                }
            },
            "required": ["url"],
        },
    },
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 3,
    },
]


def _load_system_prompt() -> str:
    """
    Load the enrichment agent system prompt from src/prompts/enrichment_system.md.

    Returns:
        The system prompt as a string.

    Raises:
        FileNotFoundError: if the prompt file does not exist.
    """
    prompt_path = Path("src/prompts/enrichment_system.md")
    return prompt_path.read_text()


def _load_enrichment_fields(country: CountryCode) -> str:
    """
    Load the country-specific enrichment field definitions.

    Reads context/enrichment_fields_{COUNTRY}.md, which is written by the
    EnrichmentResearcherAgent before this agent runs.

    Args:
        country: Country code — "US", "CA", or "AU".

    Returns:
        Markdown string of enrichment field definitions.

    Raises:
        FileNotFoundError: if the enrichment fields file does not exist.
                           Run the research phase first.
    """
    fields_path = CONTEXT_DIR / f"enrichment_fields_{country}.md"
    if not fields_path.exists():
        raise FileNotFoundError(
            f"Enrichment fields not found for {country}. "
            f"Run `python pipeline.py --phase research --country {country}` first."
        )
    return fields_path.read_text()


async def _handle_tool_call(tool_name: str, tool_input: dict) -> Any:
    """
    Dispatch a tool_use call from Claude to the appropriate Python function.

    Args:
        tool_name:  Name of the tool Claude is calling.
        tool_input: Parsed JSON input from Claude's tool_use block.

    Returns:
        Tool result as a JSON-serialisable value (str or dict).
    """
    if tool_name == "crawl_website":
        result = await crawler.crawl_website(tool_input["url"])
        return result or ""
    raise ValueError(f"Unknown tool: {tool_name}")


async def _enrich_single(
    listing: CleanListing,
    country: CountryCode,
    enrichment_fields_md: str,
    system_prompt: str,
    client: anthropic.AsyncAnthropic,
) -> EnrichedListing:
    """
    Enrich a single CleanListing using Claude + Crawl4AI.

    Steps:
      1. Build a user prompt containing listing data + field definitions
      2. Run Claude agentic tool_use loop (crawl_website / web_search)
      3. Parse Claude's final structured output into EnrichedListing fields
      4. Set enriched_at to current UTC time

    If any step fails, log the error and return an EnrichedListing with all
    enrichment fields set to null (graceful degradation).

    Args:
        listing:              The CleanListing to enrich.
        country:              Country code for this run.
        enrichment_fields_md: Markdown string of country-specific field definitions.
        system_prompt:        The enrichment agent system prompt.
        client:               Authenticated AsyncAnthropic client.

    Returns:
        EnrichedListing with extracted fields (or nulls on failure).
    """
    # TODO: Build user message: listing dict + enrichment_fields_md + country
    # TODO: Run agentic tool_use loop:
    #         while response has tool_use blocks:
    #           dispatch _handle_tool_call
    #           append tool results to messages
    #           call client.messages.create again
    # TODO: Parse final response into EnrichedListing field dict
    #         - Fields not confirmed → null (never guess)
    #         - Call Claude once more for description generation if fields extracted
    # TODO: Return EnrichedListing(**listing.model_dump(), **enrichment_fields, enriched_at=now)
    raise NotImplementedError


async def _enrich_batch(
    listings: list[CleanListing],
    country: CountryCode,
    enrichment_fields_md: str,
    system_prompt: str,
    client: anthropic.AsyncAnthropic,
) -> list[EnrichedListing]:
    """
    Enrich a batch of listings concurrently, up to CONCURRENCY at a time.

    Uses asyncio.Semaphore to cap parallel Claude + Crawl4AI calls.

    Args:
        listings:             Listings to enrich.
        country:              Country code for this run.
        enrichment_fields_md: Country-specific enrichment field definitions.
        system_prompt:        The enrichment agent system prompt.
        client:               Authenticated AsyncAnthropic client.

    Returns:
        List of EnrichedListing objects, in the same order as input.
    """
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _with_sem(listing: CleanListing) -> EnrichedListing:
        async with sem:
            return await _enrich_single(
                listing, country, enrichment_fields_md, system_prompt, client
            )

    # TODO: asyncio.gather all listings using _with_sem; return_exceptions=True
    # TODO: Log any exceptions without re-raising; return null-enriched listing instead
    raise NotImplementedError


def _write_output(
    country: CountryCode,
    enriched: list[EnrichedListing],
    run_date: str,
) -> Path:
    """
    Write enriched listings to data/enriched/{COUNTRY}/enriched_{run_date}.csv.

    Args:
        country:   Country code — used to build the output path.
        enriched:  List of EnrichedListing objects to serialise.
        run_date:  ISO date string (YYYY-MM-DD) for the filename suffix.

    Returns:
        Path to the written CSV file.
    """
    out_dir = ENRICHED_DIR / country
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"enriched_{run_date}.csv"

    # TODO: Convert to DataFrame and write CSV
    raise NotImplementedError


async def run(
    cleaned_listings: list[CleanListing],
    country: CountryCode,
) -> list[EnrichedListing]:
    """
    Run the full enrichment pipeline for a list of cleaned listings.

    Steps:
      1. Load system prompt and country-specific enrichment field definitions
      2. Initialise AsyncAnthropic client
      3. Run _enrich_batch with CONCURRENCY=5
      4. Write output CSV
      5. Print summary via rich

    Args:
        cleaned_listings: Verified listings from the clean phase.
        country:          Country code — must match the --country flag.

    Returns:
        List of EnrichedListing objects.

    Raises:
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
        FileNotFoundError: if enrichment fields or system prompt files are missing.
    """
    console.print(
        Panel(
            f"EnrichmentAgent — [bold]{country}[/bold] — {len(cleaned_listings)} listings",
            title="Enrich Phase",
        )
    )

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # TODO: _load_system_prompt()
    # TODO: _load_enrichment_fields(country)
    # TODO: anthropic.AsyncAnthropic() client
    # TODO: _enrich_batch(...)
    # TODO: _write_output(country, enriched, run_date)
    # TODO: Print rich summary
    raise NotImplementedError
