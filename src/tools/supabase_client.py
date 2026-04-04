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
    # TODO: Read SUPABASE_URL and SUPABASE_KEY from os.environ
    # TODO: Raise EnvironmentError with a clear message if either is missing
    # TODO: Return supabase.create_client(url, key)
    raise NotImplementedError


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
    # TODO: Serialise each listing to dict via .model_dump() with mode="json"
    # TODO: Call supabase.table("listings").upsert(rows, on_conflict="name,postal_code,country")
    # TODO: Collect and log any errors without raising — return them in "errors"
    # TODO: Return {"upserted": count, "errors": error_list}
    raise NotImplementedError


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
    # TODO: Query supabase.table("listings").select("*").eq("country", country)
    # TODO: Apply .range(offset, offset + limit - 1)
    # TODO: Return response.data
    raise NotImplementedError
