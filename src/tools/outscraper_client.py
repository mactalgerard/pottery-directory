"""
OutScraper API client for automated Google Maps scraping.

Implements Phase 1 (COLLECT) of the pottery-directory pipeline.

Each country runs a matrix of search terms × locations (major metros/states).
Results are deduplicated by place_id before writing to data/raw/{COUNTRY}/.

OutScraper Python SDK docs: https://github.com/outscraper/outscraper-python
API reference: https://app.outscraper.com/api-docs

Environment variable required:
  OUTSCRAPER_API_KEY — from app.outscraper.com/profile
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.models import CountryCode

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")

# ---------------------------------------------------------------------------
# Search configuration per country
# ---------------------------------------------------------------------------

# Search terms used in every country (combined with locations below)
SEARCH_TERMS: list[str] = [
    "pottery studio",
    "ceramics studio",
    "pottery classes",
    "ceramic classes",
    "clay studio",
]

# AU-specific terms override (hand building / clay classes dominate AU search)
SEARCH_TERMS_AU: list[str] = [
    "pottery studio",
    "ceramics studio",
    "clay classes",
    "hand building classes",
    "pottery classes",
    "clay studio",
]

# Major metro areas / states to search within, per country.
# OutScraper scopes results geographically when a location string is appended.
# Format: appended to search term as "{term}, {location}"
LOCATIONS: dict[CountryCode, list[str]] = {
    "US": [
        "New York, NY",
        "Los Angeles, CA",
        "Chicago, IL",
        "Houston, TX",
        "Phoenix, AZ",
        "Philadelphia, PA",
        "San Antonio, TX",
        "San Diego, CA",
        "Dallas, TX",
        "San Jose, CA",
        "Austin, TX",
        "Jacksonville, FL",
        "Fort Worth, TX",
        "Columbus, OH",
        "Charlotte, NC",
        "Indianapolis, IN",
        "San Francisco, CA",
        "Seattle, WA",
        "Denver, CO",
        "Nashville, TN",
        "Oklahoma City, OK",
        "El Paso, TX",
        "Washington, DC",
        "Las Vegas, NV",
        "Louisville, KY",
        "Memphis, TN",
        "Portland, OR",
        "Baltimore, MD",
        "Milwaukee, WI",
        "Albuquerque, NM",
        "Tucson, AZ",
        "Fresno, CA",
        "Sacramento, CA",
        "Mesa, AZ",
        "Kansas City, MO",
        "Atlanta, GA",
        "Omaha, NE",
        "Colorado Springs, CO",
        "Raleigh, NC",
        "Miami, FL",
        "Minneapolis, MN",
        "Wichita, KS",
        "Arlington, TX",
        "Boston, MA",
        "Cleveland, OH",
        "New Orleans, LA",
        "Honolulu, HI",
        "Anchorage, AK",
    ],
    "CA": [
        "Toronto, ON",
        "Montreal, QC",
        "Vancouver, BC",
        "Calgary, AB",
        "Edmonton, AB",
        "Ottawa, ON",
        "Winnipeg, MB",
        "Quebec City, QC",
        "Hamilton, ON",
        "Brampton, ON",
        "Surrey, BC",
        "Kitchener, ON",
        "Laval, QC",
        "Halifax, NS",
        "London, ON",
        "Markham, ON",
        "Vaughan, ON",
        "Gatineau, QC",
        "Longueuil, QC",
        "Burnaby, BC",
        "Saskatoon, SK",
        "Kelowna, BC",
        "Regina, SK",
        "Richmond, BC",
        "Richmond Hill, ON",
        "Oakville, ON",
        "Burlington, ON",
        "Sherbrooke, QC",
        "Oshawa, ON",
        "Victoria, BC",
    ],
    "AU": [
        "Sydney, NSW",
        "Melbourne, VIC",
        "Brisbane, QLD",
        "Perth, WA",
        "Adelaide, SA",
        "Gold Coast, QLD",
        "Newcastle, NSW",
        "Canberra, ACT",
        "Sunshine Coast, QLD",
        "Central Coast, NSW",
        "Wollongong, NSW",
        "Hobart, TAS",
        "Geelong, VIC",
        "Townsville, QLD",
        "Cairns, QLD",
        "Darwin, NT",
        "Toowoomba, QLD",
        "Ballarat, VIC",
        "Bendigo, VIC",
        "Albury, NSW",
    ],
}

# OutScraper result limit per query. 500 is practical max before costs escalate.
LIMIT_PER_QUERY = 500


# ---------------------------------------------------------------------------
# Client initialisation
# ---------------------------------------------------------------------------


def get_client():
    """
    Initialise and return an OutScraper ApiClient.

    Reads OUTSCRAPER_API_KEY from the environment.

    Returns:
        outscraper.ApiClient instance.

    Raises:
        EnvironmentError: if OUTSCRAPER_API_KEY is not set.
    """
    from outscraper import ApiClient

    api_key = os.environ.get("OUTSCRAPER_API_KEY")
    if not api_key or api_key == "your-key":
        raise EnvironmentError(
            "OUTSCRAPER_API_KEY is not set. Add it to your .env file."
        )
    return ApiClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def _build_queries(country: CountryCode) -> list[str]:
    """
    Build the full list of search query strings for a country.

    Combines search terms with locations: "{term}, {location}".
    Uses AU-specific terms for Australia.

    Args:
        country: Country code.

    Returns:
        List of search query strings, e.g. ["pottery studio, Sydney, NSW", ...]
    """
    terms = SEARCH_TERMS_AU if country == "AU" else SEARCH_TERMS
    locations = LOCATIONS[country]
    return [f"{term}, {location}" for term in terms for location in locations]


def _run_search_sync(client, query: str, limit: int) -> list[dict]:
    """
    Execute a single OutScraper Google Maps search query (synchronous).

    Wraps the OutScraper SDK call and normalises the response shape.
    OutScraper returns either a list of result dicts or a list of lists.

    Args:
        client: Initialised outscraper.ApiClient.
        query:  Search query string.
        limit:  Maximum results to return.

    Returns:
        Flat list of result dicts. Empty list on error.
    """
    try:
        results = client.google_maps_search(query, limit=limit, language="en")
        # SDK may return [[...results...]] or [...results...]
        if results and isinstance(results[0], list):
            return results[0]
        return results or []
    except Exception as exc:
        logger.warning("OutScraper query failed for %r: %s", query, exc)
        return []


def _normalise_row(raw: dict, country: CountryCode) -> dict:
    """
    Map an OutScraper result dict to the RawListing field names.

    OutScraper uses different field names than our model (e.g. "site" → "website",
    "reviews" → "reviews_count"). This function does that translation so the
    output CSV columns match what load_raw_csv() expects.

    Args:
        raw:     A single OutScraper result dict.
        country: Country code — injected into the row.

    Returns:
        Dict with keys matching RawListing fields.
    """
    return {
        "name": raw.get("name"),
        "phone": raw.get("phone"),
        "website": raw.get("site"),
        "full_address": raw.get("full_address"),
        "city": raw.get("city"),
        "state": raw.get("state") or raw.get("us_state"),
        "postal_code": raw.get("postal_code"),
        "working_hours": raw.get("working_hours"),
        "business_status": raw.get("business_status"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "reviews_count": raw.get("reviews"),
        "street_view_url": raw.get("street_view"),
        "place_id": raw.get("place_id"),  # kept for dedup; not in RawListing model
        "country": country,
    }


def _deduplicate_results(rows: list[dict]) -> list[dict]:
    """
    Remove duplicate results from a combined multi-query scrape.

    Deduplication priority:
      1. place_id (exact Google Maps identifier — most reliable)
      2. (name + postal_code) — fallback when place_id is missing

    Args:
        rows: Combined list of normalised result dicts.

    Returns:
        Deduplicated list, preserving first occurrence.
    """
    seen_place_ids: set[str] = set()
    seen_name_postal: set[tuple] = set()
    deduped: list[dict] = []

    for row in rows:
        place_id = row.get("place_id")
        name_postal = (
            (row.get("name") or "").lower().strip(),
            (row.get("postal_code") or "").strip(),
        )

        if place_id and place_id in seen_place_ids:
            continue
        if not place_id and name_postal in seen_name_postal:
            continue

        if place_id:
            seen_place_ids.add(place_id)
        seen_name_postal.add(name_postal)
        deduped.append(row)

    return deduped


# ---------------------------------------------------------------------------
# Main collect function
# ---------------------------------------------------------------------------


async def collect_listings(
    country: CountryCode,
    limit_per_query: int = LIMIT_PER_QUERY,
    dry_run: bool = False,
) -> Path:
    """
    Run the full OutScraper collect phase for a given country.

    Builds a matrix of search terms × locations, runs each query via the
    OutScraper API (synchronous SDK wrapped in asyncio thread executor),
    deduplicates results, and writes the raw CSV.

    Args:
        country:         Country code — "US", "CA", or "AU".
        limit_per_query: Max results per search query. Default 500.
        dry_run:         If True, print queries but skip API calls (for testing).

    Returns:
        Path to the written raw CSV file (data/raw/{COUNTRY}/collect_{date}.csv).

    Raises:
        EnvironmentError: if OUTSCRAPER_API_KEY is not set.
    """
    queries = _build_queries(country)
    total_queries = len(queries)
    console.print(
        f"[dim]OutScraper collect: {total_queries} queries for {country}[/dim]"
    )

    if dry_run:
        console.print("[yellow]Dry run — skipping API calls.[/yellow]")
        for q in queries:
            console.print(f"  [dim]{q}[/dim]")
        return Path(f"data/raw/{country}/collect_DRY_RUN.csv")

    client = get_client()
    loop = asyncio.get_event_loop()
    all_rows: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Scraping {country}...", total=total_queries
        )

        for i, query in enumerate(queries, 1):
            progress.update(
                task,
                description=f"[{i}/{total_queries}] {query}",
                advance=1,
            )
            raw_results = await loop.run_in_executor(
                None, _run_search_sync, client, query, limit_per_query
            )
            normalised = [_normalise_row(r, country) for r in raw_results]
            all_rows.extend(normalised)
            logger.info("Query %r → %d results", query, len(normalised))

    # Deduplicate across all queries
    before = len(all_rows)
    all_rows = _deduplicate_results(all_rows)
    after = len(all_rows)
    console.print(
        f"[green]Collected {after} unique listings "
        f"({before - after} duplicates removed across queries)[/green]"
    )

    # Drop place_id before writing — it's not part of RawListing
    for row in all_rows:
        row.pop("place_id", None)

    # Write CSV
    out_dir = RAW_DIR / country
    out_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    out_path = out_dir / f"collect_{run_date}.csv"

    df = pd.DataFrame(all_rows)
    df.to_csv(out_path, index=False)
    console.print(f"[green]Saved raw CSV → {out_path}[/green]")
    return out_path
