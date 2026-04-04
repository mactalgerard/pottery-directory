"""
pottery-directory pipeline entrypoint.

Orchestrates the four phases of the data curation pipeline:
  Phase 1 — COLLECT   OutScraper automated Google Maps scrape
  Phase 2 — CLEAN     CleanerAgent rejects invalid listings, deduplicates
  Phase 3 — ENRICH    EnrichmentAgent adds niche fields + descriptions
  Phase 4 — RESEARCH  EnrichmentResearcherAgent validates enrichment fields

Usage:
  python pipeline.py                             # Full pipeline, country=US
  python pipeline.py --country AU                # Scope entire run to Australia
  python pipeline.py --phase collect             # Scrape only for US
  python pipeline.py --country CA --phase clean  # Clean phase only for Canada
  python pipeline.py --phase enrich              # Enrich only (latest cleaned CSV)
  python pipeline.py --phase research            # Run EnrichmentResearcherAgent only
  python pipeline.py --input data/raw/AU/my.csv  # Specify input file explicitly
  python pipeline.py --to-supabase               # Upsert enriched listings to Supabase
  python pipeline.py --phase collect --dry-run   # Print queries without hitting API
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agents import cleaner_agent, enrichment_agent, enrichment_researcher, flagged_review_agent
from src.models import CleanListing, CountryCode, RawListing
from src.tools import outscraper_client, supabase_client

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

VALID_COUNTRIES: list[CountryCode] = ["US", "CA", "AU"]
VALID_PHASES = ["collect", "research", "clean", "review", "enrich"]

RAW_DIR = Path("data/raw")
CLEANED_DIR = Path("data/cleaned")


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def load_raw_csv(path: Path, country: CountryCode) -> list[RawListing]:
    """
    Load an OutScraper CSV export into a list of RawListing objects.

    Injects the `country` field at parse time — it is not present in the raw CSV.
    Raises immediately if country is not one of the three supported codes.

    Args:
        path:    Path to the OutScraper CSV file.
        country: Country code from the --country CLI flag.

    Returns:
        List of RawListing objects with country set.

    Raises:
        ValueError: if country is not a valid code.
        FileNotFoundError: if the CSV file does not exist.
    """
    if country not in VALID_COUNTRIES:
        raise ValueError(f"Invalid country: {country!r}. Must be one of {VALID_COUNTRIES}.")
    if not path.exists():
        raise FileNotFoundError(f"Raw CSV not found: {path}")

    import math

    df = pd.read_csv(path)
    records = df.to_dict(orient="records")

    listings: list[RawListing] = []
    for record in records:
        # pandas represents missing values as float NaN — convert all to None first
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None

        # Coerce numeric fields
        for field in ("latitude", "longitude"):
            if record.get(field) is not None:
                try:
                    record[field] = float(record[field])
                except (ValueError, TypeError):
                    record[field] = None
        if record.get("reviews_count") is not None:
            try:
                record["reviews_count"] = int(float(record["reviews_count"]))
            except (ValueError, TypeError):
                record["reviews_count"] = None
        # postal_code must be a string — pandas reads numeric zip codes as int
        if record.get("postal_code") is not None:
            record["postal_code"] = str(record["postal_code"])

        # Always inject country from the CLI flag — never trust the CSV value
        record["country"] = country
        try:
            listings.append(RawListing(**record))
        except Exception as exc:
            logger.warning("Skipping malformed row %r: %s", record.get("name"), exc)

    return listings


def find_latest_raw_csv(country: CountryCode) -> Path:
    """
    Find the most recently modified CSV in data/raw/{COUNTRY}/.

    Args:
        country: Country code — determines which subdirectory to search.

    Returns:
        Path to the most recently modified CSV file.

    Raises:
        FileNotFoundError: if no CSV files exist in the directory.
    """
    raw_dir = RAW_DIR / country
    csvs = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. "
            f"Drop an OutScraper export there and re-run."
        )
    return csvs[0]


def find_latest_cleaned_csv(country: CountryCode) -> Path:
    """
    Find the most recently modified cleaned CSV in data/cleaned/{COUNTRY}/.

    Only looks for files matching cleaned_{date}.csv pattern.

    Args:
        country: Country code — determines which subdirectory to search.

    Returns:
        Path to the most recently modified cleaned CSV.

    Raises:
        FileNotFoundError: if no cleaned CSVs exist (run clean phase first).
    """
    cleaned_dir = CLEANED_DIR / country
    csvs = sorted(
        cleaned_dir.glob("cleaned_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not csvs:
        raise FileNotFoundError(
            f"No cleaned CSV files found in {cleaned_dir}. "
            f"Run `python pipeline.py --country {country} --phase clean` first."
        )
    return csvs[0]


def find_latest_flagged_csv(country: CountryCode) -> Path:
    """
    Find the most recently modified flagged CSV in data/cleaned/{COUNTRY}/.

    Only looks for files matching flagged_{date}.csv pattern.

    Args:
        country: Country code — determines which subdirectory to search.

    Returns:
        Path to the most recently modified flagged CSV.

    Raises:
        FileNotFoundError: if no flagged CSVs exist (run clean phase first).
    """
    cleaned_dir = CLEANED_DIR / country
    csvs = sorted(
        cleaned_dir.glob("flagged_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not csvs:
        raise FileNotFoundError(
            f"No flagged CSV files found in {cleaned_dir}. "
            f"Run `python pipeline.py --country {country} --phase clean` first."
        )
    return csvs[0]


def load_clean_csv(path: Path, country: CountryCode) -> list[CleanListing]:
    """
    Load a cleaned or flagged CSV into a list of CleanListing objects.

    Handles NaN → None coercion and type casting for numeric and datetime fields.

    Args:
        path:    Path to the cleaned or flagged CSV.
        country: Country code — used to override the country column defensively.

    Returns:
        List of CleanListing objects.
    """
    import math

    df = pd.read_csv(path)
    records = df.to_dict(orient="records")

    listings: list[CleanListing] = []
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None

        for field in ("latitude", "longitude"):
            if record.get(field) is not None:
                try:
                    record[field] = float(record[field])
                except (ValueError, TypeError):
                    record[field] = None
        if record.get("reviews_count") is not None:
            try:
                record["reviews_count"] = int(float(record["reviews_count"]))
            except (ValueError, TypeError):
                record["reviews_count"] = None
        if record.get("postal_code") is not None:
            record["postal_code"] = str(record["postal_code"])
        if record.get("is_verified_niche") is not None:
            record["is_verified_niche"] = bool(record["is_verified_niche"])

        record["country"] = country
        try:
            listings.append(CleanListing(**record))
        except Exception as exc:
            logger.warning("Skipping malformed row %r: %s", record.get("name"), exc)

    return listings


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


async def run_collect(country: CountryCode, dry_run: bool = False, enrichment: list | None = None, max_queries: int | None = None) -> Path:
    """
    Run the OutScraper collect phase for the given country.

    Delegates to outscraper_client.collect_listings, which runs the full
    search term × location matrix and writes the raw CSV.

    Args:
        country: Country code.
        dry_run: If True, print queries but skip API calls.

    Returns:
        Path to the written raw CSV file.
    """
    return await outscraper_client.collect_listings(country, dry_run=dry_run, enrichment=enrichment, max_queries=max_queries)


async def run_research(country: CountryCode, force: bool = False) -> dict:
    """
    Run the EnrichmentResearcherAgent for the given country.

    Skipped if context/enrichment_fields_{COUNTRY}.md already exists,
    unless force=True.

    Args:
        country: Country code.
        force:   Re-run even if the context file already exists.

    Returns:
        Dict with keys "path" and "status".
    """
    return await enrichment_researcher.run(country, force=force)


async def run_clean(
    country: CountryCode,
    input_path: Path | None,
) -> tuple[list, list, list]:
    """
    Run the CleanerAgent for the given country.

    Loads the input CSV (from --input or the latest file in data/raw/{COUNTRY}/),
    runs full cleaning, and writes output CSVs.

    Args:
        country:    Country code.
        input_path: Explicit input file path, or None to use latest raw CSV.

    Returns:
        Tuple of (cleaned, flagged, rejected) CleanListing lists.
    """
    path = input_path or find_latest_raw_csv(country)
    console.print(f"[dim]Loading raw CSV: {path}[/dim]")
    raw_listings = load_raw_csv(path, country)
    return await cleaner_agent.run(raw_listings, country, str(path.name))


async def run_review(
    country: CountryCode,
    input_path: Path | None,
) -> tuple[int, int, int]:
    """
    Run the FlaggedReviewAgent for the given country.

    Loads the flagged CSV (from --input or the latest flagged_*.csv),
    reviews each listing via Claude web search, and redistributes rows
    into the cleaned / rejected / flagged CSVs in place.

    Args:
        country:    Country code.
        input_path: Explicit path to a flagged CSV, or None to use latest.

    Returns:
        Tuple of (verified_count, rejected_count, unclear_count).
    """
    path = input_path or find_latest_flagged_csv(country)
    console.print(f"[dim]Loading flagged CSV: {path}[/dim]")
    flagged_listings = load_clean_csv(path, country)

    if not flagged_listings:
        console.print(f"[yellow]No flagged listings to review in {path}[/yellow]")
        return 0, 0, 0

    return await flagged_review_agent.run(flagged_listings, country, path)


async def run_enrich(
    country: CountryCode,
    input_path: Path | None = None,
    sample: int | None = None,
    label: str = "",
) -> str:
    """
    Crawl listing websites and submit an Anthropic Batch API enrichment job.

    Loads the latest cleaned CSV (or --input), optionally samples N random
    listings, crawls their websites, and submits a batch job. Exits after
    submission — use run_retrieve() to get results when the batch is done.

    Args:
        country:    Country code.
        input_path: Explicit path to cleaned CSV, or None to use latest.
        sample:     If set, randomly select this many listings before submitting.

    Returns:
        The Anthropic batch ID.
    """
    import random
    path = input_path or find_latest_cleaned_csv(country)
    console.print(f"[dim]Loading cleaned CSV: {path}[/dim]")
    listings = load_clean_csv(path, country)

    if sample:
        listings = random.sample(listings, min(sample, len(listings)))
        console.print(f"[dim]Sampled {len(listings)} listings at random[/dim]")

    return await enrichment_agent.submit(listings, country, label=label)


def run_retrieve(country: CountryCode, label: str = "") -> tuple[bool, int, int]:
    """
    Check the Anthropic batch status and write enriched CSV if complete.

    Args:
        country: Country code.
        label:   Run label — must match the label used during submit.

    Returns:
        Tuple of (is_complete, done_count, total_count).
    """
    return enrichment_agent.retrieve(country, label=label)


async def run_poll(country: CountryCode, label: str = "") -> None:
    """
    Poll the batch status every 5 minutes until complete, then write CSV.

    Args:
        country: Country code.
        label:   Run label — must match the label used during submit.
    """
    await enrichment_agent.poll(country, label=label)


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def print_summary(
    country: CountryCode,
    total_raw: int,
    deduplicated: int,
    rejected: int,
    flagged: int,
    cleaned: int,
    enriched: int,
    supabase_result: dict | None = None,
) -> None:
    """
    Print a rich summary table at the end of the pipeline run.

    Args:
        country:         Country code for the run.
        total_raw:       Total listings in the raw CSV.
        deduplicated:    Listings removed by deduplication.
        rejected:        Listings auto-rejected by hard rules.
        flagged:         Listings flagged for human review.
        cleaned:         Verified listings written to cleaned CSV.
        enriched:        Listings successfully enriched.
        supabase_result: Result dict from upsert_listings, or None if --to-supabase not used.
    """
    table = Table(title=f"Pipeline Summary — {country}", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Total scraped", str(total_raw))
    table.add_row("Deduplicated (removed)", str(deduplicated))
    table.add_row("Auto-rejected", str(rejected))
    table.add_row("Flagged (human review)", str(flagged))
    table.add_row("Cleaned / verified", str(cleaned))
    table.add_row("Enriched", str(enriched))

    if supabase_result:
        table.add_row(
            "Upserted to Supabase",
            str(supabase_result.get("upserted", 0)),
        )
        errors = supabase_result.get("errors", [])
        if errors:
            table.add_row("[red]Supabase errors[/red]", str(len(errors)))

    console.print(table)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for the pipeline entrypoint.

    Returns:
        Parsed argparse.Namespace with attributes:
          country (str)        — US | CA | AU
          phase (str | None)   — research | clean | enrich | None (all)
          input (Path | None)  — explicit input file path
          to_supabase (bool)   — upsert enriched listings to Supabase
    """
    parser = argparse.ArgumentParser(
        description="pottery-directory data curation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--country",
        default="US",
        choices=VALID_COUNTRIES,
        help="Country to process. Default: US",
    )
    parser.add_argument(
        "--phase",
        choices=VALID_PHASES,
        default=None,
        help="Run a single phase only. Omit to run all phases.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Explicit path to input CSV. Overrides auto-discovery.",
    )
    parser.add_argument(
        "--to-supabase",
        action="store_true",
        default=False,
        help="Upsert enriched listings to Supabase after enrichment.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Collect phase only: print queries without hitting the OutScraper API.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Research phase only: re-run even if the context file already exists.",
    )
    parser.add_argument(
        "--enrichment",
        nargs="+",
        default=None,
        metavar="SERVICE",
        help="OutScraper enrichment services to apply during collect (e.g. domains_service).",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        metavar="N",
        help="Limit collect phase to first N queries. Useful for sampling.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Enrich phase: randomly select N listings before submitting batch.",
    )
    parser.add_argument(
        "--retrieve",
        action="store_true",
        default=False,
        help="Enrich phase: check batch status and write CSV if complete.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        default=False,
        help="Enrich phase: poll every 5 minutes until batch is complete, then write CSV.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="",
        metavar="NAME",
        help="Enrich phase: label for this run, appended to output filenames (e.g. 'sample10').",
    )
    return parser.parse_args()


async def main() -> None:
    """
    Main async entrypoint — parses args and orchestrates pipeline phases.

    Sequence when running all phases:
      1. Resolve country from --country flag (default: US)
      2. Load raw CSV from data/raw/{COUNTRY}/ (latest by mtime, or --input)
      3. Run EnrichmentResearcherAgent if context/enrichment_fields_{COUNTRY}.md is missing
      4. Run CleanerAgent → save to data/cleaned/{COUNTRY}/
      5. Run EnrichmentAgent concurrently → save to data/enriched/{COUNTRY}/
      6. Print summary table
      7. If --to-supabase: upsert using (name + postal_code + country) composite key
    """
    args = parse_args()
    country: CountryCode = args.country

    console.print(
        Panel(
            f"pottery-directory pipeline | country=[bold]{country}[/bold] | phase={args.phase or 'all'}",
            style="blue",
        )
    )

    # Phase: collect only
    if args.phase == "collect":
        raw_path = await run_collect(country, dry_run=args.dry_run, enrichment=args.enrichment, max_queries=args.max_queries)
        if not args.dry_run:
            console.print(f"[green]Collect complete → {raw_path}[/green]")
        return

    # Phase: research only
    if args.phase == "research":
        result = await run_research(country, force=args.force)
        if result["status"] == "written":
            console.print(f"[green]Research complete → {result['path']}[/green]")
        return

    # Phase: clean only
    if args.phase == "clean":
        cleaned, flagged, rejected = await run_clean(country, args.input)
        print_summary(
            country=country,
            total_raw=len(cleaned) + len(flagged) + len(rejected),
            deduplicated=0,  # TODO: pass actual dedup count from cleaner_agent
            rejected=len(rejected),
            flagged=len(flagged),
            cleaned=len(cleaned),
            enriched=0,
        )
        return

    # Phase: review only (optional — resolves flagged listings via web search)
    if args.phase == "review":
        verified, rejected, unclear = await run_review(country, args.input)
        console.print(
            f"[green]Review complete[/green] — "
            f"verified: {verified}, rejected: {rejected}, still unclear: {unclear}"
        )
        return

    # Phase: enrich only
    if args.phase == "enrich":
        # --retrieve (with optional --poll): check / wait for existing batch
        if args.retrieve:
            if args.poll:
                await run_poll(country, label=args.label)
            else:
                is_complete, done, total = run_retrieve(country, label=args.label)
                if not is_complete:
                    console.print(
                        f"[dim]Run with --poll to wait automatically, "
                        f"or re-run --retrieve later.[/dim]"
                    )
            return

        # Default: crawl + submit new batch
        # Auto-generate label from --sample if --label not explicitly set
        label = args.label or (f"sample{args.sample}" if args.sample else "")
        await run_enrich(country, args.input, args.sample, label=label)
        return

    # Full pipeline (all phases)
    # TODO: Step 1 — run_research(country) if enrichment_fields file is missing
    # TODO: Step 2 — run_clean(country, args.input) → cleaned, flagged, rejected
    # TODO: Step 3 — run_enrich(country) using cleaned listings
    # TODO: Step 4 — supabase_client.upsert_listings(enriched) if args.to_supabase
    # TODO: Step 5 — print_summary(...)
    raise NotImplementedError("Full pipeline not yet implemented — use --phase to run individual phases.")


if __name__ == "__main__":
    asyncio.run(main())
