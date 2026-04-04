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

from src.agents import cleaner_agent, enrichment_agent, enrichment_researcher
from src.models import CountryCode, RawListing
from src.tools import outscraper_client, supabase_client

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

VALID_COUNTRIES: list[CountryCode] = ["US", "CA", "AU"]
VALID_PHASES = ["collect", "research", "clean", "enrich"]

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

    # TODO: pd.read_csv(path)
    # TODO: For each row, build RawListing(**row_dict, country=country)
    # TODO: Collect Pydantic validation errors; log and skip malformed rows
    # TODO: Return list of valid RawListing objects
    raise NotImplementedError


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


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------


async def run_collect(country: CountryCode, dry_run: bool = False) -> Path:
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
    return await outscraper_client.collect_listings(country, dry_run=dry_run)


async def run_research(country: CountryCode) -> dict:
    """
    Run the EnrichmentResearcherAgent for the given country.

    Skipped if context/enrichment_fields_{COUNTRY}.md already exists.

    Args:
        country: Country code.

    Returns:
        Dict of confirmed enrichment field definitions.
    """
    return await enrichment_researcher.run(country)


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


async def run_enrich(country: CountryCode) -> list:
    """
    Run the EnrichmentAgent for the given country.

    Loads the latest cleaned CSV from data/cleaned/{COUNTRY}/,
    runs enrichment, and writes output CSV.

    Args:
        country: Country code.

    Returns:
        List of EnrichedListing objects.
    """
    cleaned_path = find_latest_cleaned_csv(country)
    console.print(f"[dim]Loading cleaned CSV: {cleaned_path}[/dim]")

    # TODO: pd.read_csv(cleaned_path) → list[CleanListing]
    # TODO: enrichment_agent.run(cleaned_listings, country)
    raise NotImplementedError


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
        raw_path = await run_collect(country, dry_run=args.dry_run)
        if not args.dry_run:
            console.print(f"[green]Collect complete → {raw_path}[/green]")
        return

    # Phase: research only
    if args.phase == "research":
        await run_research(country)
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

    # Phase: enrich only
    if args.phase == "enrich":
        enriched = await run_enrich(country)
        if args.to_supabase:
            result = await supabase_client.upsert_listings(enriched)
        else:
            result = None
        print_summary(
            country=country,
            total_raw=0,
            deduplicated=0,
            rejected=0,
            flagged=0,
            cleaned=len(enriched),
            enriched=len(enriched),
            supabase_result=result,
        )
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
