# pottery-directory — Claude Code Context

## What This Project Is

A data curation pipeline for building a niche directory of pottery and ceramics
studios across the US, Canada, and Australia. The pipeline has three sequential
phases:

  Phase 1 — COLLECT    Raw scrape from Google Maps via OutScraper CSV export
  Phase 2 — CLEAN      Reject invalid listings, deduplicate, verify niche match
  Phase 3 — ENRICH     Add niche-specific fields + generate listing descriptions

The output is a clean, enriched CSV (and optionally a Supabase database) ready
for import into a directory CMS.

## Critical Rules

- **Country is always explicit.** The `--country` flag (US / CA / AU) scopes
  every phase. Never infer country from data. If country is ambiguous, raise.
- **Each country is an independent run.** Enrichment field definitions, prompts,
  and price conventions differ per market and must not be mixed.
- **Agents never call Crawl4AI directly.** All crawling goes through
  `src/tools/crawler.py`.
- **Agents communicate via tool_use only** — never string parsing of LLM output.
- **Fail loud on schema violations.** Pydantic validation must run on every
  model instantiation.
- **null over invented values.** If a field cannot be confirmed from the
  website, set to null. Never guess.

## Repo Layout

```
context/                    Enrichment field definitions and niche rules (per country)
data/raw/{US,CA,AU}/        OutScraper CSV exports (gitignored)
data/cleaned/{US,CA,AU}/    Post-cleaning CSVs
data/enriched/{US,CA,AU}/   Final enriched CSVs
src/models.py               Pydantic models: RawListing, CleanListing, EnrichedListing
src/tools/crawler.py        Crawl4AI wrapper — all crawling goes here
src/tools/supabase_client.py Supabase upsert helpers
src/agents/                 Three agents: researcher, cleaner, enrichment
src/prompts/                System prompt markdown files for each agent
pipeline.py                 Main entrypoint
```

## Running the Pipeline

```bash
python pipeline.py                             # Full pipeline, country=US
python pipeline.py --country AU                # Scope entire run to Australia
python pipeline.py --phase collect             # OutScraper scrape only for US
python pipeline.py --phase collect --dry-run   # Print queries, skip API calls
python pipeline.py --country CA --phase clean  # Clean phase only for Canada
python pipeline.py --phase enrich              # Enrich only (latest cleaned CSV)
python pipeline.py --phase research            # Run EnrichmentResearcherAgent only
python pipeline.py --input data/raw/AU/my.csv  # Specify input file
python pipeline.py --to-supabase               # Upsert enriched listings to Supabase
```

## Current State

Scaffold complete — stubs only except for the collect phase.

Collect phase is fully implemented (`src/tools/outscraper_client.py`).
Run `python pipeline.py --phase collect --dry-run` to preview queries before hitting the API.

Next implementation task:
  1. Run collect phase to get real data
  2. Implement CleanerAgent rejection logic (pure Python, no LLM needed)
  3. Confirm three output CSVs (cleaned / flagged / rejected) are correct

## Tech Stack

- Python 3.11+
- `anthropic` — Claude API (claude-sonnet-4-20250514, tool_use pattern)
- `crawl4ai` — async website crawling
- `supabase` — optional storage backend
- `pydantic` — data models with validation
- `pandas` — CSV ingestion and export
- `python-dotenv` — environment variables
- `asyncio` — parallel enrichment runs
- `rich` — terminal output (panels for agent thoughts, tables for summaries)

## Supabase Table

Table: `listings`
Primary key: composite (name + postal_code + country)
Country prevents cross-market collisions between identical names/postcodes.

## Countries Supported

| Country       | Code | DataForSEO location_code | Currency |
|---------------|------|--------------------------|----------|
| United States | US   | 2840                     | USD      |
| Canada        | CA   | 2124                     | CAD      |
| Australia     | AU   | 2036                     | AUD      |
