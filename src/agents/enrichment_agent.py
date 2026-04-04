"""
EnrichmentAgent — enriches each CleanListing with niche-specific fields.

Uses the Anthropic Batch API for cost-efficient bulk processing (50% cheaper
than real-time API). The workflow is split into two steps:

  Step 1 — SUBMIT (run with python pipeline.py --phase enrich):
    1. Crawl all studio websites in parallel via Crawl4AI
    2. Build one batch request per listing with crawled content embedded
    3. Submit batch to Anthropic → save batch state to disk
    4. Exit — safe to close laptop

  Step 2 — RETRIEVE (run with python pipeline.py --phase enrich --retrieve):
    - Check batch status
    - If complete: parse results → write enriched CSV → fire macOS notification
    - If still running: print progress and exit
    - Add --poll to loop automatically every POLL_INTERVAL_SECONDS

Batch state is persisted to data/enriched/{COUNTRY}/batch_state.json so the
two steps can run in separate terminal sessions.

No web search fallback — if a crawl fails, enrichment fields are left as null.
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.models import CleanListing, CountryCode, EnrichedListing
from src.tools import crawler

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

ENRICHED_DIR = Path("data/enriched")
CONTEXT_DIR = Path("context")
MODEL = "claude-sonnet-4-6"
POLL_INTERVAL_SECONDS = 300  # 5 minutes
MAX_CRAWL_CONCURRENCY = 10

# Enrichment fields extracted via tool_use — matches EnrichedListing minus base fields
EXTRACT_FIELDS_TOOL: dict = {
    "name": "extract_fields",
    "description": (
        "Submit all extracted enrichment fields for this pottery studio listing. "
        "Call this exactly once. Use null for any field that cannot be confirmed "
        "from the website content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "class_types": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Types of classes offered, e.g. ['wheel throwing', 'hand building']",
            },
            "skill_levels": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "description": "Skill levels catered for, e.g. ['beginner', 'intermediate']",
            },
            "drop_in_available": {
                "type": ["boolean", "null"],
                "description": "True if walk-in / drop-in sessions are available without booking",
            },
            "booking_required": {
                "type": ["boolean", "null"],
                "description": "True if all sessions require advance booking",
            },
            "price_range": {
                "type": ["string", "null"],
                "description": "Relative price indicator: '$', '$$', or '$$$'",
            },
            "studio_type": {
                "type": ["string", "null"],
                "description": "e.g. 'community studio', 'private studio', 'classes only'",
            },
            "sells_supplies": {
                "type": ["boolean", "null"],
                "description": "True if the studio sells clay, glazes, or tools on-site",
            },
            "kids_classes": {
                "type": ["boolean", "null"],
                "description": "True if kids or family classes are explicitly offered",
            },
            "private_events": {
                "type": ["boolean", "null"],
                "description": "True if the studio hosts private events (birthdays, corporate, etc.)",
            },
            "open_studio_access": {
                "type": ["boolean", "null"],
                "description": "True if open studio / membership access is available for independent work",
            },
            "firing_services": {
                "type": ["boolean", "null"],
                "description": "True if kiln firing services are offered for outside/home work",
            },
            "byob_events": {
                "type": ["boolean", "null"],
                "description": "True if BYOB 'Sip & Spin' or similar social events are offered",
            },
            "date_night": {
                "type": ["boolean", "null"],
                "description": "True if couples / date night pottery sessions are explicitly offered",
            },
            "membership_model": {
                "type": ["string", "null"],
                "description": "e.g. 'monthly unlimited', 'class-based', 'firing-only', 'hourly passes'",
            },
            "description": {
                "type": ["string", "null"],
                "description": "2–3 sentence directory listing description from confirmed fields only",
            },
        },
        "required": [
            "class_types", "skill_levels", "drop_in_available", "booking_required",
            "price_range", "studio_type", "sells_supplies", "kids_classes",
            "private_events", "open_studio_access", "firing_services", "byob_events",
            "date_night", "membership_model", "description",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_system_prompt() -> str:
    path = Path("src/prompts/enrichment_system.md")
    return path.read_text()


def _load_enrichment_fields(country: CountryCode) -> str:
    path = CONTEXT_DIR / f"enrichment_fields_{country}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Enrichment fields not found for {country}. "
            f"Run `python pipeline.py --phase research --country {country}` first."
        )
    return path.read_text()


def _batch_state_path(country: CountryCode, label: str = "") -> Path:
    suffix = f"_{label}" if label else ""
    return ENRICHED_DIR / country / f"batch_state{suffix}.json"


def _batch_listings_path(country: CountryCode, run_date: str, label: str = "") -> Path:
    suffix = f"_{label}" if label else ""
    return ENRICHED_DIR / country / f"batch_listings_{run_date}{suffix}.json"


def _save_batch_state(
    country: CountryCode,
    batch_id: str,
    run_date: str,
    total: int,
    listings_file: Path,
    label: str = "",
) -> None:
    path = _batch_state_path(country, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "batch_id": batch_id,
        "run_date": run_date,
        "country": country,
        "total_requests": total,
        "submitted_at": datetime.now(tz=timezone.utc).isoformat(),
        "listings_file": str(listings_file),
        "label": label,
    }, indent=2))


def _load_batch_state(country: CountryCode, label: str = "") -> dict:
    path = _batch_state_path(country, label)
    if not path.exists():
        raise FileNotFoundError(
            f"No batch state found for {country}. "
            f"Run `python pipeline.py --phase enrich --country {country}` to submit first."
        )
    return json.loads(path.read_text())


def _notify_mac(title: str, message: str) -> None:
    """Fire a macOS notification. Silently skips on non-Mac platforms."""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # Not on macOS


def _build_user_message(
    listing: CleanListing,
    website_content: str,
    enrichment_fields_md: str,
    country: CountryCode,
) -> str:
    content_section = (
        website_content.strip()
        if website_content.strip()
        else "(Website unavailable — set all fields to null)"
    )
    return (
        f"## Studio\n"
        f"Name: {listing.name}\n"
        f"City: {listing.city or 'unknown'}\n"
        f"State: {listing.state or ''}\n"
        f"Country: {country}\n\n"
        f"## Website Content\n{content_section}\n\n"
        f"## Enrichment Field Definitions\n{enrichment_fields_md}\n\n"
        f"Extract all enrichment fields and generate the description. "
        f"Call extract_fields with your results."
    )


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


async def submit(
    listings: list[CleanListing],
    country: CountryCode,
    label: str = "",
) -> str:
    """
    Crawl all listing websites then submit an Anthropic Batch API job.

    Steps:
      1. Crawl all websites concurrently via crawl_many()
      2. Build one batch request per listing with crawled content embedded
      3. Submit batch to Anthropic API
      4. Save batch state + listings to disk

    Args:
        listings: CleanListing objects to enrich.
        country:  Country code for this run.

    Returns:
        The Anthropic batch ID string.

    Raises:
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
        FileNotFoundError: if enrichment fields file is missing.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    system_prompt = _load_system_prompt()
    enrichment_fields_md = _load_enrichment_fields(country)
    client = anthropic.Anthropic()

    # Step 1 — crawl all websites
    urls = [l.website for l in listings if l.website]
    console.print(f"[dim]Crawling {len(urls)} websites (concurrency={MAX_CRAWL_CONCURRENCY})…[/dim]")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("Crawling…", total=None)
        crawl_results = await crawler.crawl_many(urls, concurrency=MAX_CRAWL_CONCURRENCY)
        progress.update(task, description="Crawling complete")

    crawled = sum(1 for v in crawl_results.values() if v)
    console.print(f"  Crawled: {crawled}/{len(urls)} succeeded, {len(urls) - crawled} failed (will be null-enriched)")

    # Step 2 — build batch requests
    requests = []
    for i, listing in enumerate(listings):
        content = crawl_results.get(listing.website or "", "") or ""
        user_message = _build_user_message(listing, content, enrichment_fields_md, country)
        requests.append({
            "custom_id": str(i),
            "params": {
                "model": MODEL,
                "max_tokens": 1024,
                "system": system_prompt,
                "tools": [EXTRACT_FIELDS_TOOL],
                "tool_choice": {"type": "tool", "name": "extract_fields"},
                "messages": [{"role": "user", "content": user_message}],
            },
        })

    # Step 3 — submit batch
    console.print(f"[dim]Submitting batch of {len(requests)} requests…[/dim]")
    batch = client.beta.messages.batches.create(requests=requests)
    batch_id = batch.id

    # Step 4 — persist state + listings
    listings_file = _batch_listings_path(country, run_date, label)
    listings_file.parent.mkdir(parents=True, exist_ok=True)
    listings_file.write_text(json.dumps([l.model_dump(mode="json") for l in listings], indent=2))
    _save_batch_state(country, batch_id, run_date, len(requests), listings_file, label)

    retrieve_flag = f"--retrieve{f' --label {label}' if label else ''}"
    console.print(Panel(
        f"Batch submitted ✓\n\n"
        f"Batch ID:  [bold]{batch_id}[/bold]\n"
        f"Listings:  {len(requests)}\n"
        f"State:     {_batch_state_path(country, label)}\n\n"
        f"You can close your laptop.\n"
        f"Run [bold]python pipeline.py --phase enrich {retrieve_flag} --country {country}[/bold] to check status.",
        title="Enrich Phase — Submitted",
        style="green",
    ))

    return batch_id


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------


def _clean_string_fields(fields: dict) -> dict:
    """Strip accidental surrounding quotes from string field values."""
    cleaned = {}
    for k, v in fields.items():
        if isinstance(v, str):
            stripped = v.strip().strip('"').strip("'")
            cleaned[k] = stripped if stripped else None
        else:
            cleaned[k] = v
    return cleaned


def _parse_batch_results(
    batch_id: str,
    listings: list[CleanListing],
    country: CountryCode,
    client: anthropic.Anthropic,
) -> list[EnrichedListing]:
    """
    Download batch results and merge with original listings.

    For each result:
      - succeeded: parse extract_fields tool_use input → EnrichedListing
      - errored/expired: log and return null-enriched listing

    Returns:
        List of EnrichedListing objects in the same order as listings.
    """
    now = datetime.now(tz=timezone.utc)
    results_by_id: dict[str, dict] = {}

    for result in client.beta.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            message = result.result.message
            tool_uses = [b for b in message.content if b.type == "tool_use" and b.name == "extract_fields"]
            if tool_uses:
                results_by_id[result.custom_id] = tool_uses[0].input
            else:
                logger.warning("No extract_fields call in result for custom_id=%s", result.custom_id)
                results_by_id[result.custom_id] = {}
        else:
            logger.warning(
                "Batch result %s: type=%s", result.custom_id, result.result.type
            )
            results_by_id[result.custom_id] = {}

    enriched: list[EnrichedListing] = []
    for i, listing in enumerate(listings):
        fields = _clean_string_fields(results_by_id.get(str(i), {}))
        try:
            enriched.append(EnrichedListing(
                **listing.model_dump(),
                enriched_at=now,
                **fields,
            ))
        except Exception as exc:
            logger.warning("Failed to build EnrichedListing for %r: %s", listing.name, exc)
            enriched.append(EnrichedListing(**listing.model_dump(), enriched_at=now))

    return enriched


def _write_enriched_csv(
    enriched: list[EnrichedListing],
    country: CountryCode,
    run_date: str,
    label: str = "",
) -> Path:
    suffix = f"_{label}" if label else ""
    out_dir = ENRICHED_DIR / country
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"enriched_{run_date}{suffix}.csv"
    pd.DataFrame([e.model_dump() for e in enriched]).to_csv(out_path, index=False)
    return out_path


def retrieve(country: CountryCode, label: str = "") -> tuple[bool, int, int]:
    """
    Check the batch status for the given country.

    If the batch is complete, parses results, writes enriched CSV, and fires
    a macOS notification.

    Args:
        country: Country code.

    Returns:
        Tuple of (is_complete, done_count, total_count).

    Raises:
        FileNotFoundError: if no batch state exists (submit first).
        EnvironmentError: if ANTHROPIC_API_KEY is not set.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    state = _load_batch_state(country, label)
    batch_id = state["batch_id"]
    run_date = state["run_date"]
    total = state["total_requests"]
    label = state.get("label", label)
    client = anthropic.Anthropic()

    batch = client.beta.messages.batches.retrieve(batch_id)
    counts = batch.request_counts
    done = counts.succeeded + counts.errored + counts.expired
    in_progress = batch.processing_status == "in_progress"

    if in_progress:
        console.print(
            f"[yellow]Batch in progress[/yellow] — "
            f"{done}/{total} complete "
            f"({counts.succeeded} succeeded, {counts.errored} errored, {counts.expired} expired)"
        )
        return False, done, total

    # Batch ended — parse and write
    console.print(f"[green]Batch complete[/green] — {done}/{total} results")

    listings_file = Path(state["listings_file"])
    raw = json.loads(listings_file.read_text())
    listings = [CleanListing(**r) for r in raw]

    enriched = _parse_batch_results(batch_id, listings, country, client)
    out_path = _write_enriched_csv(enriched, country, run_date, label)

    table = Table(title=f"Enrich Phase — {country}", show_lines=True)
    table.add_column("Outcome", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[green]Succeeded[/green]", str(counts.succeeded))
    table.add_row("[red]Errored[/red]", str(counts.errored))
    table.add_row("[yellow]Expired[/yellow]", str(counts.expired))
    table.add_row("Total enriched", str(len(enriched)))
    console.print(table)
    console.print(f"[green]→ {out_path}[/green]")

    _notify_mac(
        "pottery-directory",
        f"{country} enrichment complete — {len(enriched)} listings written.",
    )

    return True, done, total


async def poll(country: CountryCode, label: str = "") -> None:
    """
    Poll the batch status every POLL_INTERVAL_SECONDS until complete.

    Prints a status line on each check. When the batch finishes, calls
    retrieve() to write the CSV and fire the macOS notification, then exits.

    Args:
        country: Country code.
    """
    console.print(
        f"[dim]Polling every {POLL_INTERVAL_SECONDS // 60} minutes. "
        f"Leave this terminal open and close your laptop.[/dim]"
    )
    while True:
        is_complete, done, total = retrieve(country, label)
        if is_complete:
            break
        console.print(f"  [dim]{datetime.now().strftime('%H:%M:%S')} — next check in {POLL_INTERVAL_SECONDS // 60} min[/dim]")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
