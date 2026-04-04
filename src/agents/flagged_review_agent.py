"""
FlaggedReviewAgent — resolves flagged listings via Claude web search.

Flagged listings are listings that passed all hard rejection rules but could
not be niche-verified because they have no website. This agent uses Claude's
native web_search tool to look up each business by name and location, then
returns a structured verdict.

Verdicts:
  verified  — confirmed pottery/ceramics studio → appended to cleaned CSV
  rejected  — confirmed non-pottery business   → appended to rejected CSV
  unclear   — inconclusive evidence            → stays in flagged CSV

Input:  data/cleaned/{COUNTRY}/flagged_{date}.csv
Output: modifies the three cleaned-phase CSVs in place:
          data/cleaned/{COUNTRY}/cleaned_{date}.csv  ← verified rows appended
          data/cleaned/{COUNTRY}/rejected_{date}.csv ← rejected rows appended
          data/cleaned/{COUNTRY}/flagged_{date}.csv  ← overwritten with unclear only

Concurrency: up to CONCURRENCY listings reviewed in parallel.
Rules: context/niche_verification_rules.md
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import anthropic
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.models import CleanListing, CountryCode

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

CLEANED_DIR = Path("data/cleaned")
MODEL = "claude-sonnet-4-6"
CONCURRENCY = 1          # Web search responses are large; 1 concurrent avoids rate limits
RETRY_DELAYS = [60, 120] # Seconds to wait before retry 1 and retry 2 on 429

Verdict = Literal["verified", "rejected", "unclear"]

TOOLS: list[dict] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 2,
    },
    {
        "name": "submit_verdict",
        "description": (
            "Submit your final verdict on whether this business is a pottery or ceramics studio. "
            "Call this exactly once after completing your research."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["verified", "rejected", "unclear"],
                    "description": (
                        "'verified' = confirmed pottery/ceramics studio offering classes or open studio access. "
                        "'rejected' = confirmed non-pottery business (restaurant, supply-only shop, unrelated). "
                        "'unclear' = inconclusive — not enough evidence to decide either way."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "One sentence explaining the verdict. Cite the source (e.g. website, Google Maps).",
                },
            },
            "required": ["verdict", "reason"],
        },
    },
]

SYSTEM_PROMPT = """\
You are a research assistant verifying whether a business is a legitimate pottery or ceramics studio.

A business qualifies as VERIFIED if it:
- Offers pottery or ceramics classes (wheel throwing, hand building, glazing, etc.)
- Provides open studio access or studio memberships
- Operates as a community ceramics studio

A business should be REJECTED if it is:
- A restaurant, clothing store, or clearly unrelated business
- A general craft supply retailer (Michaels-type) with no pottery focus
- A paint-your-own pottery venue (Color Me Mine-type) — no wheel/hand-building
- A school or university ceramics department with no public access

Mark as UNCLEAR only when you genuinely cannot determine the business type from search results.

Research process:
1. Search for the business by name and location
2. Read the search results
3. Call submit_verdict with your finding

Be decisive. Most businesses are clearly one thing or another.
"""


async def _create_with_retry(
    client: anthropic.AsyncAnthropic,
    messages: list,
) -> anthropic.types.Message:
    """
    Call client.messages.create, retrying on 429 rate-limit errors.

    Waits RETRY_DELAYS[i] seconds before each retry attempt. If all retries
    are exhausted, re-raises the last RateLimitError.

    Args:
        client:   Authenticated AsyncAnthropic client.
        messages: Current conversation messages list.

    Returns:
        The API response message.

    Raises:
        anthropic.RateLimitError: if all retry attempts fail.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            console.print(f"  [yellow]Rate limit hit — waiting {delay}s before retry {attempt}…[/yellow]")
            await asyncio.sleep(delay)
        try:
            return await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.RateLimitError as exc:
            last_exc = exc
            logger.warning("Rate limit on attempt %d: %s", attempt + 1, exc)
    raise last_exc


async def _review_single(
    listing: CleanListing,
    client: anthropic.AsyncAnthropic,
) -> tuple[CleanListing, Verdict, str]:
    """
    Review a single flagged listing using Claude web search.

    Sends Claude a prompt with the listing details, lets it run up to 2
    web searches, then expects a submit_verdict tool call.

    Falls back to verdict="unclear" if Claude does not call submit_verdict
    or if any exception is raised.

    Args:
        listing: The flagged CleanListing to review.
        client:  Authenticated AsyncAnthropic client.

    Returns:
        Tuple of (listing, verdict, reason).
    """
    location = ", ".join(filter(None, [listing.city, listing.state, listing.country]))
    user_message = (
        f"Business name: {listing.name}\n"
        f"Location: {location}\n"
        f"Phone: {listing.phone or 'not available'}\n\n"
        f"Search for this business and determine whether it is a pottery or ceramics studio. "
        f"Then call submit_verdict with your finding."
    )

    messages = [{"role": "user", "content": user_message}]

    try:
        while True:
            response = await _create_with_retry(client, messages)

            # Collect tool calls from this response turn
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                # Claude stopped without calling submit_verdict
                logger.warning("No tool call from Claude for %r — marking unclear", listing.name)
                return listing, "unclear", "Claude did not return a verdict"

            # Append assistant turn
            messages.append({"role": "assistant", "content": response.content})

            # Process tool results
            tool_results = []
            verdict_result: tuple[Verdict, str] | None = None

            for tool_use in tool_uses:
                if tool_use.name == "submit_verdict":
                    verdict_result = (
                        tool_use.input["verdict"],
                        tool_use.input["reason"],
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": "Verdict recorded.",
                    })
                # web_search is handled server-side — no client-side dispatch needed

            if verdict_result:
                return listing, verdict_result[0], verdict_result[1]

            # If no submit_verdict yet, append tool results and continue loop
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Guard against infinite loops
            if len(messages) > 12:
                logger.warning("Message loop too long for %r — marking unclear", listing.name)
                return listing, "unclear", "Review loop exceeded message limit"

    except Exception as exc:
        logger.error("Error reviewing %r: %s", listing.name, exc)
        return listing, "unclear", f"Review failed: {exc}"


async def run(
    flagged_listings: list[CleanListing],
    country: CountryCode,
    flagged_path: Path,
) -> tuple[int, int, int]:
    """
    Review all flagged listings and redistribute them into the three output CSVs.

    Each listing is written to its destination CSV immediately after its verdict
    is returned — the flagged CSV is also updated in place after every step.
    This means progress is preserved if the run is interrupted.

    Flagged CSV at any point in time contains:
      - Listings not yet reviewed
      - Listings reviewed as unclear

    The date suffix is derived from the flagged_path filename so that all
    three output files stay in sync (e.g. flagged_2026-04-04.csv → *_2026-04-04.csv).

    Args:
        flagged_listings: CleanListing objects loaded from the flagged CSV.
        country:          Country code for this run.
        flagged_path:     Path to the flagged CSV being processed.

    Returns:
        Tuple of (verified_count, rejected_count, unclear_count).

    Raises:
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    console.print(
        Panel(
            f"FlaggedReviewAgent — [bold]{country}[/bold] — {len(flagged_listings)} flagged listings",
            title="Review Phase",
        )
    )

    # Derive sibling paths from the flagged filename (e.g. flagged_2026-04-04.csv)
    date_suffix = flagged_path.name.replace("flagged_", "")  # → 2026-04-04.csv
    out_dir = flagged_path.parent
    cleaned_path = out_dir / f"cleaned_{date_suffix}"
    rejected_path = out_dir / f"rejected_{date_suffix}"

    client = anthropic.AsyncAnthropic()

    verified_count = 0
    rejected_count = 0
    unclear_count = 0

    # Tracks which listings are still in the flagged CSV (unreviewed + unclear).
    # Starts as the full list; resolved listings are removed as we go.
    remaining: list[CleanListing] = list(flagged_listings)

    for i, listing in enumerate(flagged_listings):
        console.print(f"  [dim]({i + 1}/{len(flagged_listings)})[/dim] {listing.name} ({listing.city})")

        _, verdict, reason = await _review_single(listing, client)

        now = datetime.now(tz=timezone.utc)

        console.print(
            f"    [{_verdict_colour(verdict)}]{verdict.upper()}[/] — {reason}"
        )

        if verdict == "verified":
            resolved = listing.model_copy(update={
                "is_verified_niche": True,
                "rejection_reason": None,
                "cleaned_at": now,
            })
            _append_to_csv([resolved], cleaned_path)
            remaining.remove(listing)
            verified_count += 1

        elif verdict == "rejected":
            resolved = listing.model_copy(update={
                "is_verified_niche": False,
                "rejection_reason": f"review: {reason}",
                "cleaned_at": now,
            })
            _append_to_csv([resolved], rejected_path)
            remaining.remove(listing)
            rejected_count += 1

        else:
            unclear_count += 1

        # Rewrite flagged CSV after every listing — contains unreviewed + unclear
        pd.DataFrame([l.model_dump() for l in remaining]).to_csv(flagged_path, index=False)

    # Summary
    table = Table(title=f"Review Phase — {country}", show_lines=True)
    table.add_column("Outcome", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]Verified → cleaned[/green]", str(verified_count))
    table.add_row("[red]Rejected → rejected[/red]", str(rejected_count))
    table.add_row("[yellow]Unclear → stays flagged[/yellow]", str(unclear_count))
    console.print(table)

    if verified_count:
        console.print(f"[green]→ {verified_count} rows appended to {cleaned_path}[/green]")
    if rejected_count:
        console.print(f"[red]→ {rejected_count} rows appended to {rejected_path}[/red]")
    if unclear_count:
        console.print(f"[yellow]→ {unclear_count} rows remain in {flagged_path}[/yellow]")

    return verified_count, rejected_count, unclear_count


def _append_to_csv(listings: list[CleanListing], path: Path) -> None:
    """Append listings to an existing CSV, or create it if it doesn't exist."""
    if not listings:
        return
    new_df = pd.DataFrame([l.model_dump() for l in listings])
    if path.exists():
        existing = pd.read_csv(path)
        pd.concat([existing, new_df], ignore_index=True).to_csv(path, index=False)
    else:
        new_df.to_csv(path, index=False)


def _verdict_colour(verdict: Verdict) -> str:
    return {"verified": "green", "rejected": "red", "unclear": "yellow"}[verdict]
