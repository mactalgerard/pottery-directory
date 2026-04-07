# pottery-directory — Claude Code Context

## What This Project Is

A data curation pipeline for building a niche directory of pottery and ceramics
studios across the US, Canada, and Australia. The pipeline has five sequential
phases:

  Phase 1 — COLLECT    Automated OutScraper Google Maps scrape (with domains_service enrichment)
  Phase 2 — CLEAN      Hard rules, deduplication, Crawl4AI keyword-based niche verification
  Phase 3 — REVIEW     Resolve flagged listings (no-website) via Claude web_search tool
  Phase 4 — RESEARCH   Validate enrichment field definitions per country (Claude + web search)
  Phase 5 — ENRICH     Crawl websites, extract niche fields, generate descriptions (Batch API)

Output: enriched CSVs in `data/enriched/{COUNTRY}/` and optionally upserted to Supabase.

## Critical Rules

- **Country is always explicit.** The `--country` flag (US / CA / AU) scopes
  every phase. Never infer country from data. If country is ambiguous, raise.
- **Each country is an independent run.** Prompts and price conventions are
  country-scoped and must not be mixed.
- **Enrichment fields are uniform across all countries.** The same 14 fields apply
  to US, CA, and AU. Do not add country-specific fields without updating all three
  context files and the Supabase schema.
- **Agents never call Crawl4AI directly.** All crawling goes through
  `src/tools/crawler.py`.
- **Agents communicate via tool_use only** — never string parsing of LLM output.
- **Fail loud on schema violations.** Pydantic validation must run on every
  model instantiation.
- **null over invented values.** If a field cannot be confirmed from the
  website, set to null. Never guess.

## Repo Layout

```
context/                         Enrichment field definitions and niche rules (per country)
  enrichment_fields_{US,CA,AU}.md  All three validated; uniform 14-field schema across countries
  niche_verification_rules.md      Keyword rules used by CleanerAgent crawl verification
data/raw/{US,CA,AU}/             OutScraper CSV exports (gitignored)
data/cleaned/{US,CA,AU}/         cleaned / flagged / rejected CSVs
data/enriched/{US,CA,AU}/        Final enriched CSVs + batch state JSON files
supabase/migrations/             SQL migration files (001_create_listings_table.sql)
src/models.py                    Pydantic models: RawListing, CleanListing, EnrichedListing
src/tools/
  crawler.py                     Crawl4AI wrapper — all crawling goes here
  outscraper_client.py           OutScraper Google Maps API automation
  supabase_client.py             Supabase CRUD helpers
src/agents/
  cleaner_agent.py               Hard rules + dedup + Crawl4AI niche verification
  flagged_review_agent.py        Resolves no-website flagged listings via web search
  enrichment_researcher.py       Validates enrichment fields per country (runs once)
  enrichment_agent.py            Batch API enrichment — submit + retrieve/poll
src/prompts/                     System prompt markdown files for each agent
pipeline.py                      Main entrypoint
```

## Running the Pipeline

```bash
# Collect
python pipeline.py --phase collect --country US
python pipeline.py --phase collect --dry-run          # Preview queries, skip API
python pipeline.py --phase collect --max-queries 10   # Sample first N queries

# Clean
python pipeline.py --phase clean --country US

# Review flagged listings
python pipeline.py --phase review --country US

# Research (validate enrichment fields — skips if context file exists)
python pipeline.py --phase research --country US
python pipeline.py --phase research --country US --force  # Re-run even if file exists

# Enrich (Batch API — two steps)
python pipeline.py --phase enrich --country US               # Submit batch
python pipeline.py --phase enrich --country US --sample 10   # Submit sample of 10
python pipeline.py --phase enrich --country US --retrieve     # Check status / write CSV
python pipeline.py --phase enrich --country US --retrieve --poll  # Auto-poll every 5 min
python pipeline.py --phase enrich --country US --label v2     # Tag run with label

# Supabase
python pipeline.py --to-supabase --country US                 # Upsert latest enriched CSV
python pipeline.py --to-supabase --country US --input data/enriched/US/enriched_2026-04-04.csv
python pipeline.py --delete-country --country CA              # Bulk delete (with confirmation)

# Specify input file explicitly for any phase
python pipeline.py --phase clean --country US --input data/raw/US/my.csv
```

## Current State

All three country pipelines fully complete end-to-end.

**Phase 4 (research) is skipped for CA and AU** — enrichment fields are pre-validated
with the same 14-field schema as US. Context files at `context/enrichment_fields_{CA,AU}.md`
are already populated; no agent run needed.

| Phase    | US  | CA | AU |
|----------|-----|----|----|
| collect  | ✅  | ✅ | ✅ |
| clean    | ✅  | ✅ | ✅ |
| review   | ✅  | ✅ | ✅ |
| research | ✅  | ✅ | ✅ |
| enrich   | ✅  | ✅ | ✅ |
| supabase | ✅  | ✅ | ✅ |

US enriched output: `data/enriched/US/enriched_2026-04-04.csv` — 1,993 rows, 67.5% enriched.
Supabase upsert confirmed complete as of 2026-04-05 — all 1,993 US listings live in the `listings` table.

AU enriched output: `data/enriched/AU/enriched_2026-04-06.csv` — 330 rows (cleaned from 359), 78.3% enriched.
Supabase upsert confirmed complete as of 2026-04-06 — all 330 AU listings live in the `listings` table.
29 US-state contaminated rows and 10 state abbreviation rows removed during 2026-04-06 data quality pass.

CA raw: `data/raw/CA/collect_2026-04-06.csv` — 830 rows.
CA cleaned: `data/cleaned/CA/cleaned_2026-04-06.csv` — 440 rows after review phase (388 from clean + verified from flagged review).
CA enriched output: `data/enriched/CA/enriched_2026-04-06.csv` — 440 rows, 78.0% partially enriched, 22.0% zero-enrichment (crawl failures).
Supabase upsert confirmed complete as of 2026-04-07 — all 440 CA listings live in the `listings` table.
5 province abbreviation rows (ON, MB, AB) manually normalised to full names before upsert on 2026-04-07.

**Note on US data quality:** The 1,993-row enriched CSV was produced before Crawl4AI niche
verification was implemented. Some borderline listings (paint-your-own, supply-only) may be
present. A re-run of clean + enrich will produce a tighter dataset but is not required before
website work begins.

## Website

The frontend website (ClayFinder) is a separate project located at `~/Desktop/Projects/clayfinder`.
See `clayfinder/CLAUDE.md` for full website context.

Key decisions made during 2026-04-05 planning session:
- Domain: `clayfinder.com` (registered via Porkbun)
- Keyword cluster validated via DataForSEO — see `context/keyword_cluster.md`
- Primary keywords: "pottery classes near me" (KD 4, 110k SV) + "ceramics classes near me" (KD 3, 110k SV)
- Main competitor: ClassBento (marketplace model, not a free directory)
- Monetization: display ads primary, lead gen secondary at 10k+/month traffic

## Key Implementation Details

### Collect Phase
- Uses `domains_service` enrichment — populates `website` and `email` fields on every row
- Output CSV deleted at the start of each run — prevents duplicate rows from appended re-runs on the same date
- Incremental CSV writes per query — progress preserved if interrupted mid-run
- 60s `asyncio.wait_for` timeout per query — slow/failing queries logged and skipped
- Query matrix: US 240 (5 terms × 48 metros), CA 150 (5 × 30), AU 120 (6 × 20)
- AU uses different search terms (`clay classes`, `hand building classes`)
- **CA locations use `"City, Province, Canada"` format** (e.g. `"London, Ontario, Canada"`) — prevents
  OutScraper from resolving ambiguous city names to foreign countries (London UK, Burlington VT, etc.)
- `postal_code` coerced to `str` at ingest — pandas reads numeric zip codes as int
- All CSV loaders use `math.isnan` check to convert `float NaN` → `None` before Pydantic instantiation

### Clean Phase
- Hard rules: `_is_closed`, `_is_incomplete_address`, `_is_missing_contact`, `_is_wrong_region`
- `_is_missing_hours` deliberately excluded — too aggressive for Google Maps data quality
- `_is_wrong_region(listing, country)` rejects listings whose `state` field is non-null and not in
  `_VALID_REGIONS[country]` — catches geographic contamination from ambiguous OutScraper queries
- `_normalise_state(state, country)` expands abbreviations to full names (ON→Ontario, VIC→Victoria,
  etc.) using `_STATE_ABBREVIATIONS` dict — applied before hard rules so all output CSVs use
  consistent full-name states
- Dedup: phone → address+postal+country → lat/lng within 50m (Haversine)
- Niche verification: `crawl_many(concurrency=10)` batch-crawls all websites, then
  `_verify_niche(listing, content)` applies keyword heuristics from `context/niche_verification_rules.md`
- Three output CSVs: `cleaned_`, `flagged_`, `rejected_`

### Niche Verification Keywords
- **Positive:** pottery, ceramics, clay, wheel throwing, kiln, glazing, hand building, open studio, etc.
- **Supply-only flag:** pottery supplies, pottery supply, ceramic supplies, kilns for sale
- **Paint-your-own flag:** paint your own, color me mine
- **Hard negative (reject):** restaurant, real estate, michaels, hobby lobby

### FlaggedReviewAgent
- Uses Claude `web_search_20250305` native tool
- `submit_verdict` custom tool with structured output: `verified` / `rejected` / `unclear`
- `CONCURRENCY = 1` — sequential to avoid 30k tokens/min rate limit
- Retry with exponential backoff on 429 errors (`[60, 120]` seconds)
- Per-row incremental CSV writes — restartable if interrupted

### EnrichmentResearcherAgent
- Model: `claude-opus-4-6` (runs once per country)
- Web search with `max_uses: 10`
- Skips if `context/enrichment_fields_{COUNTRY}.md` exists unless `--force`
- US fields validated: 9 original + 5 new (open_studio_access, firing_services, byob_events, date_night, membership_model)
- **CA and AU skip this phase** — context files pre-populated with the same 14-field schema on 2026-04-06;
  only currency labels and country-specific notes differ

### EnrichmentAgent (Batch API)
- Step 1 (submit): crawl all websites → embed content in batch requests → `extract_fields` tool with `tool_choice: forced`
- Step 2 (retrieve): `--retrieve` checks once; `--retrieve --poll` loops every 5 min with macOS notification
- Batch state persisted to `data/enriched/{COUNTRY}/batch_state{_label}.json`
- `--sample N` auto-sets label to `sampleN` — isolated from full run files
- `_clean_string_fields()` strips accidental surrounding quotes from string values
- No web search fallback — crawl failures → null enrichment fields (null over invention)
- MAX_CONTENT_CHARS = 12,000 (~3,000 tokens) — truncated in `crawler.py`
- `crawl_many` uses a hard outer timeout (`asyncio.wait_for(crawl_website(...), timeout=timeout+10)`) — catches DNS/connection hangs that bypass Playwright's `page_timeout`
- `load_enriched_csv` uses `ast.literal_eval` to parse `class_types` and `skill_levels` back from CSV string representation to proper Python lists before Pydantic validation

### Supabase
- Table: `listings`, composite PK: `(name, postal_code, country)`
- Migration: `supabase/migrations/001_create_listings_table.sql`
- All sync supabase-py calls wrapped in `asyncio.to_thread()`
- `upsert_listings`: `on_conflict="name,postal_code,country"` — idempotent re-runs
- `--to-supabase` is a standalone CLI step (no `--phase` required)
- `--delete-country` bulk deletes all rows for a country with confirmation prompt
- Single-row deletes: use `delete_listing()` directly or the Supabase dashboard
- **RLS is disabled** on the `listings` table — not needed for a backend-only pipeline table
- `anon` and `authenticated` roles have SELECT only — INSERT/UPDATE/DELETE revoked
- `service_role` key retains full write access and is what the pipeline uses

## Tech Stack

- Python 3.11+
- `anthropic` — Claude API (tool_use pattern + Batch API)
- `crawl4ai` 0.8.6 — async website crawling (`fit_markdown` output)
- `supabase` ≥2.0.0 — Postgres storage backend
- `pydantic` — data models with strict validation
- `pandas` — CSV ingestion and export
- `python-dotenv` — environment variables
- `asyncio` — concurrency (crawl_many semaphore, batch polling)
- `rich` — terminal output (panels, tables, progress)
- `outscraper` — Google Maps API client

## Models

| Model | Agent | Rationale |
|-------|-------|-----------|
| `claude-opus-4-6` | EnrichmentResearcherAgent | Runs once; quality matters |
| `claude-sonnet-4-6` | EnrichmentAgent, FlaggedReviewAgent | Cost/quality balance for batch work |

## Supabase Environment Variables

```
SUPABASE_URL   — https://your-project.supabase.co
SUPABASE_KEY   — service role key (not the anon key)
```

## Countries Supported

| Country       | Code | Currency | OutScraper queries |
|---------------|------|----------|--------------------|
| United States | US   | USD      | 240 (5 × 48 metros) |
| Canada        | CA   | CAD      | 150 (5 × 30 metros) |
| Australia     | AU   | AUD      | 120 (6 × 20 metros) |
