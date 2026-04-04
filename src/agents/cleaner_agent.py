"""
CleanerAgent — validates and deduplicates raw listings.

Takes a list of RawListing objects and a country code. Applies hard rejection
rules (pure Python, no LLM needed), then verifies niche match via Crawl4AI
for listings that have a website. Deduplicates on phone, address, and lat/lng.

Output split:
  data/cleaned/{COUNTRY}/cleaned_{date}.csv   — verified listings
  data/cleaned/{COUNTRY}/flagged_{date}.csv   — needs human review
  data/cleaned/{COUNTRY}/rejected_{date}.csv  — auto-rejected with reasons

Rules defined in: context/niche_verification_rules.md
"""

import asyncio
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.models import CleanListing, CountryCode, RawListing
from src.tools import crawler

console = Console()
logger = logging.getLogger(__name__)

CLEANED_DIR = Path("data/cleaned")

# Distance threshold for lat/lng deduplication (metres)
DEDUP_RADIUS_METRES = 50


# ---------------------------------------------------------------------------
# Hard rejection rules (pure Python — no LLM, no network)
# ---------------------------------------------------------------------------


def _is_closed(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if the listing's business_status indicates closure.

    Checks for "temporarily closed" and "permanently closed" (case-insensitive).

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if closed, else None.
    """
    # TODO: Check listing.business_status against closed statuses
    raise NotImplementedError


def _is_missing_hours(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if working_hours is null or empty.

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if hours are missing, else None.
    """
    # TODO: Check listing.working_hours for None / empty string
    raise NotImplementedError


def _is_incomplete_address(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if the address is missing or incomplete.

    An address is considered complete if full_address is non-empty OR
    (city and postal_code are both present).

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if address is incomplete, else None.
    """
    # TODO: Evaluate full_address, city, postal_code
    raise NotImplementedError


def _is_missing_contact(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if BOTH phone AND website are missing.

    A listing with at least one contact method is acceptable.

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if both phone and website are absent, else None.
    """
    # TODO: Check listing.phone and listing.website
    raise NotImplementedError


def _apply_hard_rules(listing: RawListing) -> Optional[str]:
    """
    Run all hard rejection rules against a single listing.

    Stops at the first matching rule (rules are not cumulative).

    Args:
        listing: The RawListing to evaluate.

    Returns:
        The first rejection reason found, or None if the listing passes all rules.
    """
    for check in [
        _is_closed,
        _is_missing_hours,
        _is_incomplete_address,
        _is_missing_contact,
    ]:
        reason = check(listing)
        if reason:
            return reason
    return None


# ---------------------------------------------------------------------------
# Niche verification (via Crawl4AI)
# ---------------------------------------------------------------------------


async def _verify_niche(listing: RawListing) -> tuple[bool, Optional[str]]:
    """
    Confirm the listing is a pottery/ceramics studio by crawling its website.

    Verification outcomes:
      (True, None)              — confirmed pottery/ceramics studio
      (False, "flag: ...")      — pottery supply retailer without studio access
                                  (needs human review, not auto-rejected)
      (False, "rejected: ...")  — general craft store, unrelated business

    If the listing has no website, returns (False, "flag: no website to verify").

    Args:
        listing: The RawListing whose website will be crawled.

    Returns:
        Tuple of (is_verified_niche, rejection_or_flag_reason).
    """
    if not listing.website:
        return False, "flag: no website — manual niche verification required"

    # TODO: Call crawler.crawl_website(listing.website)
    # TODO: If crawl returns None, return (False, "flag: website crawl failed")
    # TODO: Apply keyword heuristics to confirm pottery/ceramics niche:
    #         - Positive signals: "pottery", "ceramics", "clay", "wheel throwing",
    #           "hand building", "kiln", "glazing", "studio membership"
    #         - Supply-only signals: "pottery supplies", "clay supplies", "kiln for sale"
    #           without studio/class language → flag
    #         - Negative signals: unrelated business → reject
    # TODO: Return appropriate (bool, reason) tuple
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in metres between two lat/lng points.

    Uses the Haversine formula. Suitable for short distances (< 1 km).

    Args:
        lat1, lon1: Coordinates of the first point (decimal degrees).
        lat2, lon2: Coordinates of the second point (decimal degrees).

    Returns:
        Distance in metres as a float.
    """
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def deduplicate(listings: list[RawListing], country: CountryCode) -> list[RawListing]:
    """
    Remove duplicate listings using three matching strategies.

    Deduplication keys (evaluated in order — first match wins):
      1. Phone number (exact match, non-null)
      2. (full_address + postal_code + country) — country prevents cross-market collisions
      3. Lat/lng within DEDUP_RADIUS_METRES (50 m)

    When duplicates are found, keep the listing with more non-null fields.
    Log each duplicate that is dropped, including the matching key used.

    Args:
        listings: List of RawListing objects for a single country.
        country:  Country code — used as part of the address dedup key.

    Returns:
        De-duplicated list of RawListing objects.
    """
    # TODO: Build seen_phones: dict[str, RawListing]
    # TODO: Build seen_addresses: dict[tuple, RawListing]
    # TODO: Build seen_coords: list[tuple[float, float, RawListing]] for radius check
    # TODO: For each listing, check all three keys; drop if matched, else add to seen sets
    # TODO: When keeping the "more complete" listing, count non-None fields
    # TODO: Log duplicates with logger.info
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_outputs(
    country: CountryCode,
    cleaned: list[CleanListing],
    flagged: list[CleanListing],
    rejected: list[CleanListing],
    run_date: str,
) -> tuple[Path, Path, Path]:
    """
    Write the three output CSVs for a cleaning run.

    Paths:
      data/cleaned/{COUNTRY}/cleaned_{run_date}.csv
      data/cleaned/{COUNTRY}/flagged_{run_date}.csv
      data/cleaned/{COUNTRY}/rejected_{run_date}.csv

    Args:
        country:  Country code — used to build output paths.
        cleaned:  Verified listings.
        flagged:  Listings needing human review.
        rejected: Auto-rejected listings.
        run_date: ISO date string (YYYY-MM-DD) for filename suffix.

    Returns:
        Tuple of (cleaned_path, flagged_path, rejected_path).
    """
    out_dir = CLEANED_DIR / country
    out_dir.mkdir(parents=True, exist_ok=True)

    # TODO: Convert each list to pd.DataFrame via [l.model_dump() for l in listings]
    # TODO: Write each DataFrame to CSV with index=False
    # TODO: Return the three Path objects
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run(
    raw_listings: list[RawListing],
    country: CountryCode,
    source_file: str,
) -> tuple[list[CleanListing], list[CleanListing], list[CleanListing]]:
    """
    Run the full cleaning pipeline for a list of raw listings.

    Steps:
      1. Deduplicate raw_listings
      2. Apply hard rejection rules (pure Python)
      3. Verify niche for listings that pass hard rules (Crawl4AI)
      4. Classify each listing as cleaned / flagged / rejected
      5. Write output CSVs
      6. Print summary table via rich

    Args:
        raw_listings: Listings loaded from an OutScraper CSV.
        country:      Country code — must match the --country flag used at ingest.
        source_file:  Filename of the raw CSV (stored in CleanListing.source_file).

    Returns:
        Tuple of (cleaned, flagged, rejected) lists of CleanListing objects.
    """
    console.print(
        Panel(
            f"CleanerAgent — [bold]{country}[/bold] — {len(raw_listings)} raw listings",
            title="Clean Phase",
        )
    )

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # TODO: Step 1 — deduplicate
    # TODO: Step 2 — apply hard rules; collect rejections
    # TODO: Step 3 — async niche verification for survivors
    # TODO: Step 4 — build CleanListing objects; route to cleaned / flagged / rejected
    # TODO: Step 5 — _write_outputs(...)
    # TODO: Step 6 — print rich summary table: total / deduplicated / rejected / flagged / cleaned
    raise NotImplementedError
