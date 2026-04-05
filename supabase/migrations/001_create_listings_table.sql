-- Migration: 001_create_listings_table
-- Creates the listings table for the pottery-directory pipeline.
--
-- Composite primary key (name, postal_code, country) prevents cross-market
-- collisions between listings that share identical names and postcodes across
-- different countries, and allows idempotent upserts on re-runs.
--
-- Run this in the Supabase SQL editor before executing:
--   python pipeline.py --to-supabase --country US

create table if not exists listings (

  -- ---------------------------------------------------------------------------
  -- Identity
  -- ---------------------------------------------------------------------------
  name            text        not null,
  country         text        not null,  -- 'US' | 'CA' | 'AU'

  -- ---------------------------------------------------------------------------
  -- Raw fields (from OutScraper via collect phase)
  -- ---------------------------------------------------------------------------
  phone           text,
  email           text,
  website         text,
  full_address    text,
  city            text,
  state           text,
  postal_code     text,
  working_hours   text,
  business_status text,
  latitude        double precision,
  longitude       double precision,
  reviews_count   integer,
  street_view_url text,

  -- ---------------------------------------------------------------------------
  -- Clean fields (added by CleanerAgent)
  -- ---------------------------------------------------------------------------
  is_verified_niche boolean  not null,
  rejection_reason  text,
  source_file       text     not null,
  cleaned_at        timestamptz,

  -- ---------------------------------------------------------------------------
  -- Enrichment fields (added by EnrichmentAgent)
  -- text[] maps to list[str] in the Pydantic model; supabase-py handles the
  -- JSON array → Postgres array conversion automatically.
  -- ---------------------------------------------------------------------------
  class_types        text[],
  skill_levels       text[],
  drop_in_available  boolean,
  booking_required   boolean,
  price_range        text,       -- '$' | '$$' | '$$$'
  studio_type        text,       -- 'community studio' | 'private studio' | 'classes only'
  sells_supplies     boolean,
  kids_classes       boolean,
  private_events     boolean,

  -- US-validated additional fields
  open_studio_access boolean,
  firing_services    boolean,
  byob_events        boolean,
  date_night         boolean,
  membership_model   text,

  -- Generated description (never scraped — always synthesised from structured fields)
  description        text,

  -- ---------------------------------------------------------------------------
  -- Metadata
  -- ---------------------------------------------------------------------------
  enriched_at        timestamptz,

  -- ---------------------------------------------------------------------------
  -- Composite primary key
  -- ---------------------------------------------------------------------------
  primary key (name, postal_code, country)

);
