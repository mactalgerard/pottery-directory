# pottery-directory

A data curation pipeline for building a niche directory of pottery and ceramics
studios across the US, Canada, and Australia.

## Pipeline Overview

```
Phase 1 — COLLECT    OutScraper Google Maps CSV export (manual step)
Phase 2 — CLEAN      Reject invalid listings, deduplicate, verify niche match
Phase 3 — ENRICH     Add niche-specific fields + generate listing descriptions
```

Each country (US, CA, AU) is treated as an independent pipeline run.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Full pipeline for US (default)
python pipeline.py

# Full pipeline for Australia
python pipeline.py --country AU

# Clean phase only for Canada
python pipeline.py --country CA --phase clean

# Enrich only (uses latest cleaned CSV)
python pipeline.py --phase enrich

# Run enrichment researcher agent only
python pipeline.py --phase research

# Specify input file explicitly
python pipeline.py --input data/raw/AU/my_export.csv

# Upsert enriched listings to Supabase
python pipeline.py --to-supabase
```

## Data Flow

```
data/raw/{COUNTRY}/          ← Drop OutScraper CSV exports here
data/cleaned/{COUNTRY}/      ← Cleaned, flagged, and rejected CSVs
data/enriched/{COUNTRY}/     ← Final enriched listings
context/enrichment_fields_*.md  ← Country-specific field definitions (auto-generated)
```

## Supported Countries

| Country       | Code | Currency |
|---------------|------|----------|
| United States | US   | USD      |
| Canada        | CA   | CAD      |
| Australia     | AU   | AUD      |
