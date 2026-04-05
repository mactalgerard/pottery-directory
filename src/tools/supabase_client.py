"""
Supabase client helpers for the pottery-directory pipeline.

Assumes the following table exists in Supabase:

  Table: listings
  Primary key: composite (name, postal_code, country)

The composite key prevents cross-market collisions between listings that share
identical names and postcodes across different countries.

Environment variables required:
  SUPABASE_URL  — e.g. https://your-project.supabase.co
  SUPABASE_KEY  — service role key (not the anon key)
"""

import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console

from src.models import EnrichedListing

load_dotenv()
console = Console()
logger = logging.getLogger(__name__)


def get_client():
    """
    Initialise and return an authenticated Supabase client.

    Reads SUPABASE_URL and SUPABASE_KEY from the environment.
    Raises EnvironmentError if either variable is missing.

    Returns:
        A supabase.Client instance ready for queries.
    """
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_KEY must be set in environment or .env file"
        )
    return create_client(url, key)


async def upsert_listings(listings: list[EnrichedListing]) -> dict:
    """
    Upsert a batch of EnrichedListing objects into the Supabase `listings` table.

    Uses (name + postal_code + country) as the composite conflict key so that
    re-running the pipeline updates existing records rather than duplicating them.

    Args:
        listings: List of EnrichedListing objects to upsert.

    Returns:
        Dict with keys:
          "upserted" (int)  — number of rows successfully upserted
          "errors"   (list) — list of error dicts for any rows that failed
    """
    client = get_client()
    rows = [l.model_dump(mode="json") for l in listings]
    errors = []

    def _do_upsert():
        return (
            client.table("listings")
            .upsert(rows, on_conflict="name,postal_code,country")
            .execute()
        )

    try:
        response = await asyncio.to_thread(_do_upsert)
        upserted = len(response.data) if response.data else len(rows)
    except Exception as exc:
        logger.error("Supabase upsert failed: %s", exc)
        errors.append({"error": str(exc), "rows": len(rows)})
        upserted = 0

    if errors:
        logger.warning("%d upsert error(s) encountered", len(errors))

    return {"upserted": upserted, "errors": errors}


async def delete_listing(name: str, postal_code: str, country: str) -> dict:
    """
    Delete a single listing by its composite primary key.

    Args:
        name:        Listing name.
        postal_code: Postal code string.
        country:     Country code — "US", "CA", or "AU".

    Returns:
        Dict with keys:
          "deleted" (int)  — 1 if the row was found and deleted, 0 otherwise
          "errors"  (list) — list of error dicts if the operation failed
    """
    client = get_client()
    errors = []

    def _do_delete():
        return (
            client.table("listings")
            .delete()
            .eq("name", name)
            .eq("postal_code", postal_code)
            .eq("country", country)
            .execute()
        )

    try:
        response = await asyncio.to_thread(_do_delete)
        deleted = len(response.data) if response.data else 0
    except Exception as exc:
        logger.error("Supabase delete_listing failed: %s", exc)
        errors.append({"error": str(exc)})
        deleted = 0

    return {"deleted": deleted, "errors": errors}


async def delete_listings_by_country(country: str) -> dict:
    """
    Bulk delete all listings for a country.

    Intended as a reset before re-importing a cleaner dataset. Use with care —
    this removes every row for the given country with no further confirmation.

    Args:
        country: Country code — "US", "CA", or "AU".

    Returns:
        Dict with keys:
          "deleted" (int)  — number of rows deleted
          "errors"  (list) — list of error dicts if the operation failed
    """
    client = get_client()
    errors = []

    def _do_delete():
        return (
            client.table("listings")
            .delete()
            .eq("country", country)
            .execute()
        )

    try:
        response = await asyncio.to_thread(_do_delete)
        deleted = len(response.data) if response.data else 0
    except Exception as exc:
        logger.error("Supabase delete_listings_by_country failed: %s", exc)
        errors.append({"error": str(exc)})
        deleted = 0

    return {"deleted": deleted, "errors": errors}


async def query_listings(
    country: str,
    limit: int = 1000,
    offset: int = 0,
) -> list[dict]:
    """
    Query enriched listings from Supabase filtered by country.

    Args:
        country: Country code — "US", "CA", or "AU".
        limit:   Maximum rows to return per call. Default 1000.
        offset:  Row offset for pagination. Default 0.

    Returns:
        List of raw dicts from Supabase (not yet cast to EnrichedListing).
    """
    client = get_client()

    def _do_query():
        return (
            client.table("listings")
            .select("*")
            .eq("country", country)
            .range(offset, offset + limit - 1)
            .execute()
        )

    response = await asyncio.to_thread(_do_query)
    return response.data or []
