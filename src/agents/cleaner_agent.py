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

# Abbreviation → full name mappings per country.
# Applied during cleaning so all output CSVs use consistent full names.
_STATE_ABBREVIATIONS: dict[str, dict[str, str]] = {
    "AU": {
        "NSW": "New South Wales",
        "VIC": "Victoria",
        "QLD": "Queensland",
        "WA": "Western Australia",
        "SA": "South Australia",
        "TAS": "Tasmania",
        "ACT": "Australian Capital Territory",
        "NT": "Northern Territory",
    },
    "CA": {
        "ON": "Ontario",
        "BC": "British Columbia",
        "QC": "Quebec",
        "AB": "Alberta",
        "MB": "Manitoba",
        "SK": "Saskatchewan",
        "NS": "Nova Scotia",
        "NB": "New Brunswick",
        "PE": "Prince Edward Island",
        "NL": "Newfoundland and Labrador",
        "NT": "Northwest Territories",
        "YT": "Yukon",
        "YK": "Yukon",
        "NU": "Nunavut",
    },
    "US": {},  # US abbreviations are standard and widely accepted — no expansion needed
}

# Valid province/state/territory values per country.
# Includes both full names and common abbreviations as OutScraper returns either.
_VALID_REGIONS: dict[str, set[str]] = {
    "CA": {
        # Full names
        "Ontario", "British Columbia", "Quebec", "Alberta", "Manitoba",
        "Saskatchewan", "Nova Scotia", "New Brunswick", "Prince Edward Island",
        "Newfoundland and Labrador", "Northwest Territories", "Yukon", "Nunavut",
        # Abbreviations
        "ON", "BC", "QC", "AB", "MB", "SK", "NS", "NB", "PE", "NL", "NT", "YT", "YK", "NU",
    },
    "AU": {
        # Full names
        "New South Wales", "Victoria", "Queensland", "Western Australia",
        "South Australia", "Tasmania", "Australian Capital Territory",
        "Northern Territory",
        # Abbreviations
        "NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT",
    },
    "US": {
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
        "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
        "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
        "New Hampshire", "New Jersey", "New Mexico", "New York",
        "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
        "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
        "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
        # Abbreviations
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
        "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
        "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
        "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
        "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    },
}


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
    if listing.business_status and "closed" in listing.business_status.lower():
        return f"business_status: {listing.business_status}"
    return None


def _is_missing_hours(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if working_hours is null or empty.

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if hours are missing, else None.
    """
    if not listing.working_hours or not str(listing.working_hours).strip():
        return "missing working hours"
    return None


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
    has_full = bool(listing.full_address and listing.full_address.strip())
    has_city_and_postal = bool(
        listing.city and listing.city.strip()
        and listing.postal_code and listing.postal_code.strip()
    )
    if not has_full and not has_city_and_postal:
        return "incomplete address (missing full_address and city/postal_code)"
    return None


def _normalise_state(state: Optional[str], country: CountryCode) -> Optional[str]:
    """
    Expand a state/province abbreviation to its full name for the given country.

    Returns the state unchanged if no mapping exists (including already-full names).
    Returns None if state is null or empty.

    Args:
        state:   Raw state/province string from OutScraper.
        country: Country code — selects the abbreviation mapping to use.

    Returns:
        Full-name state string, or None if state is absent.
    """
    if not state or not state.strip():
        return state
    mapping = _STATE_ABBREVIATIONS.get(country, {})
    return mapping.get(state.strip(), state.strip())


def _is_wrong_region(listing: RawListing, country: CountryCode) -> Optional[str]:
    """
    Return a rejection reason if the listing's state/province is not valid for
    the target country.

    Only rejects when the state field is non-null and does not match any known
    province/state/territory for the country. Listings with a null state pass
    through (they are caught later by _is_incomplete_address or manual review).

    Args:
        listing: The RawListing to evaluate.
        country: The expected country code.

    Returns:
        Rejection reason string if the region is wrong, else None.
    """
    valid = _VALID_REGIONS.get(country)
    if valid is None:
        return None  # no allowlist defined for this country — skip check

    state = (listing.state or "").strip()
    if not state:
        return None  # null/empty state — let other rules handle it

    if state not in valid:
        return f"wrong region: state/province '{state}' is not a valid {country} province/territory"

    return None


def _is_missing_contact(listing: RawListing) -> Optional[str]:
    """
    Return a rejection reason if BOTH phone AND website are missing.

    A listing with at least one contact method is acceptable.

    Args:
        listing: The RawListing to evaluate.

    Returns:
        Rejection reason string if both phone and website are absent, else None.
    """
    has_phone = bool(listing.phone and listing.phone.strip())
    has_website = bool(listing.website and listing.website.strip())
    if not has_phone and not has_website:
        return "no contact method (phone and website both missing)"
    return None


def _apply_hard_rules(listing: RawListing, country: CountryCode) -> Optional[str]:
    """
    Run all hard rejection rules against a single listing.

    Stops at the first matching rule (rules are not cumulative).

    Args:
        listing: The RawListing to evaluate.
        country: Country code — used for geographic region validation.

    Returns:
        The first rejection reason found, or None if the listing passes all rules.
    """
    for check in [
        _is_closed,
        _is_incomplete_address,
        _is_missing_contact,
        lambda l: _is_wrong_region(l, country),
    ]:
        reason = check(listing)
        if reason:
            return reason
    return None


# ---------------------------------------------------------------------------
# Niche verification (keyword heuristics on pre-crawled content)
# ---------------------------------------------------------------------------

# Positive signals — any match confirms this is a pottery/ceramics venue
_POSITIVE_KEYWORDS = [
    "pottery", "ceramics", "ceramic", "clay", "wheel throwing",
    "kiln", "glazing", "hand building", "clay classes", "potter",
    "stoneware", "earthenware", "throwing", "open studio",
    "atelier de poterie", "céramique", "poterie",  # CA French
]

# Supply-only signals — retailer without a working studio
_SUPPLY_ONLY_SIGNALS = [
    "pottery supplies", "pottery supply", "ceramic supplies",
    "kilns for sale", "clay supplier",
]

# Studio/class signals — counterweigh supply-only signals if present
_STUDIO_SIGNALS = [
    "classes", "workshop", "studio", "lessons", "membership",
    "open studio", "wheel", "throw", "hand build",
]

# Paint-your-own — different activity, flag for human review
_PAINT_YOUR_OWN_SIGNALS = [
    "paint your own", "paint-your-own", "color me mine", "painting pottery",
    "painted pottery",
]

# Hard negatives — clearly unrelated; reject only when no positive keywords present
_HARD_NEGATIVE_KEYWORDS = [
    "restaurant", "real estate", "michaels", "hobby lobby",
    "art supply store", "arts and crafts supply",
]


def _verify_niche(listing: RawListing, content: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Confirm the listing is a pottery/ceramics studio using pre-crawled website content.

    Verification outcomes:
      (True, None)              — confirmed pottery/ceramics studio
      (False, "flag: ...")      — needs human review (crawl failed, paint-your-own,
                                  supply-only, or no matching keywords)
      (False, "rejected: ...")  — clearly unrelated business

    Args:
        listing: The RawListing being evaluated.
        content: Pre-crawled website markdown (or None if crawl failed / no website).

    Returns:
        Tuple of (is_verified_niche, rejection_or_flag_reason).
    """
    if not listing.website:
        return False, "flag: no website — manual niche verification required"

    if content is None:
        return False, "flag: crawl failed — manual niche verification required"

    text = content.lower()

    has_positive = any(kw in text for kw in _POSITIVE_KEYWORDS)
    has_negative = any(kw in text for kw in _HARD_NEGATIVE_KEYWORDS)
    has_paint_your_own = any(kw in text for kw in _PAINT_YOUR_OWN_SIGNALS)
    has_supply_only = any(kw in text for kw in _SUPPLY_ONLY_SIGNALS)
    has_studio = any(kw in text for kw in _STUDIO_SIGNALS)

    if has_negative and not has_positive:
        return False, "rejected: unrelated business"

    if has_paint_your_own:
        return False, "flag: paint-your-own pottery — manual niche verification required"

    if has_supply_only and not has_studio:
        return False, "flag: pottery supply retailer — no studio/classes evidence"

    if has_positive:
        return True, None

    return False, "flag: no pottery keywords found in website content"


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
    seen_phones: set[str] = set()
    seen_addresses: set[tuple] = set()
    seen_coords: list[tuple[float, float]] = []
    deduped: list[RawListing] = []

    for listing in listings:
        phone = (listing.phone or "").strip()
        if phone and phone in seen_phones:
            logger.info("Duplicate (phone): %r", listing.name)
            continue

        addr_key = (
            (listing.full_address or "").lower().strip(),
            (listing.postal_code or "").strip(),
            country,
        )
        if addr_key[0] and addr_key in seen_addresses:
            logger.info("Duplicate (address): %r", listing.name)
            continue

        if listing.latitude is not None and listing.longitude is not None:
            is_duplicate = False
            for lat, lon in seen_coords:
                dist = _haversine_metres(listing.latitude, listing.longitude, lat, lon)
                if dist <= DEDUP_RADIUS_METRES:
                    logger.info("Duplicate (lat/lng, %.1fm): %r", dist, listing.name)
                    is_duplicate = True
                    break
            if is_duplicate:
                continue
            seen_coords.append((listing.latitude, listing.longitude))

        if phone:
            seen_phones.add(phone)
        if addr_key[0]:
            seen_addresses.add(addr_key)

        deduped.append(listing)

    return deduped


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

    paths = []
    for label, lst in [("cleaned", cleaned), ("flagged", flagged), ("rejected", rejected)]:
        path = out_dir / f"{label}_{run_date}.csv"
        pd.DataFrame([l.model_dump() for l in lst]).to_csv(path, index=False)
        paths.append(path)

    return tuple(paths)


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

    # Step 1 — deduplicate
    before = len(raw_listings)
    deduped = deduplicate(raw_listings, country)
    dedup_removed = before - len(deduped)

    # Step 2 — apply hard rules
    passed: list[RawListing] = []
    rejected: list[CleanListing] = []
    for listing in deduped:
        normalised_state = _normalise_state(listing.state, country)
        if normalised_state != listing.state:
            listing = listing.model_copy(update={"state": normalised_state})
        reason = _apply_hard_rules(listing, country)
        if reason:
            rejected.append(CleanListing(
                **listing.model_dump(),
                is_verified_niche=False,
                rejection_reason=reason,
                source_file=source_file,
            ))
        else:
            passed.append(listing)

    # Step 3 — niche verification
    # Batch-crawl all websites, then apply keyword heuristics per listing.
    console.print(f"[dim]Crawling {sum(1 for l in passed if l.website)} websites for niche verification…[/dim]")
    urls_to_crawl = [l.website for l in passed if l.website]
    crawl_results: dict[str, Optional[str]] = {}
    if urls_to_crawl:
        crawl_results = await crawler.crawl_many(urls_to_crawl, concurrency=10)

    cleaned: list[CleanListing] = []
    flagged: list[CleanListing] = []
    for listing in passed:
        content = crawl_results.get(listing.website) if listing.website else None
        verified, flag_reason = _verify_niche(listing, content)
        if verified:
            cleaned.append(CleanListing(
                **listing.model_dump(),
                is_verified_niche=True,
                rejection_reason=None,
                source_file=source_file,
            ))
        else:
            flagged.append(CleanListing(
                **listing.model_dump(),
                is_verified_niche=False,
                rejection_reason=flag_reason,
                source_file=source_file,
            ))

    # Step 4 — write outputs
    cleaned_path, flagged_path, rejected_path = _write_outputs(
        country, cleaned, flagged, rejected, run_date
    )

    # Step 5 — summary table
    table = Table(title=f"Clean Phase — {country}", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("Total raw", str(before))
    table.add_row("Deduplicated (removed)", str(dedup_removed))
    table.add_row("Hard-rejected", str(len(rejected)))
    table.add_row("Flagged (human review)", str(len(flagged)))
    table.add_row("Cleaned / verified", str(len(cleaned)))
    console.print(table)
    console.print(f"[green]→ {cleaned_path}[/green]")
    console.print(f"[yellow]→ {flagged_path}[/yellow]")
    console.print(f"[red]→ {rejected_path}[/red]")

    return cleaned, flagged, rejected
