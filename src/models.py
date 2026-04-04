"""
Pydantic data models for the pottery-directory pipeline.

Three models represent the three pipeline stages:
  RawListing      — direct mapping from OutScraper Google Maps CSV export
  CleanListing    — post-cleaning, with niche verification result
  EnrichedListing — final enriched listing ready for CMS import
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


CountryCode = Literal["US", "CA", "AU"]


class RawListing(BaseModel):
    """
    Direct mapping from an OutScraper Google Maps CSV export row.

    The `country` field is NOT present in the raw CSV — it is injected at
    ingest time from the --country CLI flag. If country is not explicitly
    provided, the pipeline must raise immediately rather than infer.
    """

    name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    full_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    working_hours: Optional[str] = None
    business_status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reviews_count: Optional[int] = None
    street_view_url: Optional[str] = None
    country: CountryCode = Field(
        ...,
        description="Injected at ingest time from --country flag. Never inferred.",
    )


class CleanListing(RawListing):
    """
    A RawListing that has passed (or been evaluated against) the cleaning rules.

    Listings are split into three buckets post-cleaning:
      - Verified: is_verified_niche=True, rejection_reason=None
      - Flagged:  is_verified_niche=False, rejection_reason set, needs human review
      - Rejected: auto-rejected by hard rules, rejection_reason set
    """

    is_verified_niche: bool = Field(
        ...,
        description="True if confirmed as a pottery/ceramics studio, False if rejected or flagged.",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Human-readable rejection or flag reason. None for verified listings.",
    )
    source_file: str = Field(
        ...,
        description="Filename of the raw CSV this listing originated from.",
    )
    cleaned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the cleaning step ran for this listing.",
    )


class EnrichedListing(CleanListing):
    """
    A CleanListing with niche-specific pottery enrichment fields added.

    All enrichment fields are Optional — they are populated from website crawl
    data and may be null if the information cannot be confirmed. Never invent
    or guess a value; prefer null over speculation.

    The field set below represents hypothesised fields validated by the
    EnrichmentResearcherAgent before enrichment begins. The researcher agent
    may add or remove fields per country; the model should remain flexible.

    Description is always generated fresh from confirmed structured fields —
    never copy-pasted from the business website.
    """

    # --- Class / session structure ---
    class_types: Optional[list[str]] = Field(
        default=None,
        description="Types of classes offered, e.g. ['wheel throwing', 'hand building', 'glazing'].",
    )
    skill_levels: Optional[list[str]] = Field(
        default=None,
        description="Skill levels catered for, e.g. ['beginner', 'intermediate', 'advanced'].",
    )

    # --- Booking / access ---
    drop_in_available: Optional[bool] = Field(
        default=None,
        description="True if walk-in / drop-in sessions are available without prior booking.",
    )
    booking_required: Optional[bool] = Field(
        default=None,
        description="True if all sessions require advance booking.",
    )

    # --- Pricing ---
    price_range: Optional[str] = Field(
        default=None,
        description="Market-relative price indicator: '$', '$$', or '$$$'.",
    )

    # --- Studio type ---
    studio_type: Optional[str] = Field(
        default=None,
        description="One of: 'community studio', 'private studio', 'classes only'.",
    )

    # --- Retail / extras ---
    sells_supplies: Optional[bool] = Field(
        default=None,
        description="True if the studio sells pottery supplies on-site.",
    )
    kids_classes: Optional[bool] = Field(
        default=None,
        description="True if kids or family classes are explicitly offered.",
    )
    private_events: Optional[bool] = Field(
        default=None,
        description="True if the studio hosts private events (birthdays, corporate, etc.).",
    )

    # --- Generated description ---
    description: Optional[str] = Field(
        default=None,
        description=(
            "2–3 sentence listing description generated from confirmed structured fields only. "
            "Never scraped or copy-pasted from the business website. "
            "Tone should feel local to the country."
        ),
    )

    # --- Metadata ---
    enriched_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when enrichment ran for this listing.",
    )
