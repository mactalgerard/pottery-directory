# pottery-directory

A data curation pipeline for building a niche directory of pottery and ceramics
studios across the US, Canada, and Australia.

## Pipeline Overview

```
Phase 1 — COLLECT    Automated OutScraper Google Maps scrape (with domains_service enrichment)
Phase 2 — CLEAN      Hard rules, deduplication, Crawl4AI niche verification
Phase 3 — REVIEW     Resolve flagged listings (no-website) via Claude web search
Phase 4 — RESEARCH   Validate enrichment field definitions per country via Claude + web search
Phase 5 — ENRICH     Crawl websites, extract niche fields, generate descriptions (Batch API)
```

Each country (US, CA, AU) is treated as an independent pipeline run. Output CSVs can
optionally be upserted to Supabase.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:

| Variable | Purpose |
|----------|---------|
| `OUTSCRAPER_API_KEY` | OutScraper Google Maps API |
| `ANTHROPIC_API_KEY` | Claude API (clean review, research, enrich) |
| `SUPABASE_URL` | Supabase project URL (optional — only needed for `--to-supabase`) |
| `SUPABASE_KEY` | Supabase service role key (optional) |

## Usage

### Collect

```bash
# Preview queries without hitting the API
python pipeline.py --phase collect --dry-run

# Full US collect (240 queries, ~2,400 listings)
python pipeline.py --phase collect --country US

# Limit to first N queries for sampling
python pipeline.py --phase collect --country US --max-queries 10
```

### Clean

```bash
# Run cleaner — applies hard rules, deduplicates, crawls websites for niche verification
python pipeline.py --phase clean --country US

# Outputs three CSVs to data/cleaned/US/:
#   cleaned_{date}.csv   — verified pottery studios
#   flagged_{date}.csv   — needs human review (no website, crawl failed, ambiguous)
#   rejected_{date}.csv  — auto-rejected (closed, incomplete, unrelated)
```

### Review (flagged listings)

```bash
# Resolve flagged listings via Claude web search
python pipeline.py --phase review --country US

# Use a specific flagged file
python pipeline.py --phase review --country US --input data/cleaned/US/flagged_2026-04-04.csv
```

### Research

```bash
# Validate enrichment field definitions for a country (runs once, skips if file exists)
python pipeline.py --phase research --country US

# Force re-run even if the context file already exists
python pipeline.py --phase research --country US --force
```

### Enrich (Batch API — two steps)

```bash
# Step 1: crawl websites and submit batch job
python pipeline.py --phase enrich --country US

# Submit a random sample of 10 listings (isolated output files)
python pipeline.py --phase enrich --country US --sample 10

# Step 2: check if batch is done and write enriched CSV
python pipeline.py --phase enrich --country US --retrieve

# Step 2 (auto-poll every 5 min, macOS notification when complete)
python pipeline.py --phase enrich --country US --retrieve --poll

# Tag a run with a label (appended to output filenames)
python pipeline.py --phase enrich --country US --label v2
```

### Supabase upsert

```bash
# Upsert latest enriched CSV to Supabase (standalone — run after enrich --retrieve)
python pipeline.py --to-supabase --country US

# Upsert a specific file
python pipeline.py --to-supabase --country US --input data/enriched/US/enriched_2026-04-04.csv
```

### Supabase delete

```bash
# Delete all listings for a country (prompts for confirmation — destructive)
python pipeline.py --delete-country --country CA
```

For single-row deletions, use the Supabase dashboard or call `delete_listing()` directly.

## Data Flow

```
data/raw/{COUNTRY}/             ← OutScraper CSVs written by collect phase
data/cleaned/{COUNTRY}/         ← cleaned / flagged / rejected CSVs from clean + review phases
data/enriched/{COUNTRY}/        ← enriched CSVs + batch state from enrich phase
context/enrichment_fields_*.md  ← country-specific field definitions (written by research phase)
context/niche_verification_rules.md  ← keyword rules for Crawl4AI niche verification
src/prompts/                    ← system prompt markdown files for each agent
```

## Agents

| Agent | File | Purpose |
|-------|------|---------|
| CleanerAgent | `src/agents/cleaner_agent.py` | Hard rules, dedup, Crawl4AI niche verification |
| FlaggedReviewAgent | `src/agents/flagged_review_agent.py` | Resolves no-website listings via Claude web search |
| EnrichmentResearcherAgent | `src/agents/enrichment_researcher.py` | Validates enrichment fields per country |
| EnrichmentAgent | `src/agents/enrichment_agent.py` | Batch API enrichment — crawl + field extraction + description |

## Supported Countries

| Country       | Code | Currency | OutScraper queries |
|---------------|------|----------|--------------------|
| United States | US   | USD      | 240 (5 terms × 48 metros) |
| Canada        | CA   | CAD      | 150 (5 terms × 30 metros) |
| Australia     | AU   | AUD      | 120 (6 terms × 20 metros) |

## Current Status

| Country | Collect | Clean | Review | Research | Enrich | Supabase |
|---------|---------|-------|--------|----------|--------|----------|
| US      | ✅      | ✅    | ✅     | ✅       | ✅     | —        |
| CA      | —       | —     | —      | —        | —      | —        |
| AU      | —       | —     | —      | —        | —      | —        |
