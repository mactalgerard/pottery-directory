# Session Summary — 2026-04-04 (Part 2)

## What We Did

---

### 1. Virtual Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Verified Collect Phase (Dry Run)

Confirmed 240 queries (5 terms × 48 US metros) printed correctly without hitting the API.

```bash
python pipeline.py --phase collect --dry-run
```

---

### 3. Ran Real Collect Phase (US)

First run without enrichment. Produced `data/raw/US/collect_2026-04-04.csv` with **2,433 rows** but **0 website URLs** — OutScraper's base Google Maps result did not populate the `site` field for any listing.

**Cost breakdown from invoice:**
- First 500 results: $0.00 (free tier)
- Remaining ~312 at $0.003/result = ~$0.94 billed
- Projected full run cost: ~$11–12

---

### 4. Implemented `load_raw_csv()` in `pipeline.py`

Maps OutScraper CSV rows → `RawListing` objects with country injected from the CLI flag. Key issues fixed during implementation:

| Bug | Fix |
|-----|-----|
| `float('nan')` passed to Pydantic string fields | Explicit `math.isnan` check before Pydantic instantiation |
| `postal_code` read as `int` by pandas | Explicit `str()` coercion after NaN cleanup |

---

### 5. Implemented `CleanerAgent` (pure Python phase)

Implemented all stubs in `src/agents/cleaner_agent.py`:

**Hard rejection rules** (`_apply_hard_rules`):
- `_is_closed()` — rejects if `business_status` contains "closed" (case-insensitive)
- `_is_incomplete_address()` — rejects if no `full_address` AND no `city` + `postal_code`
- `_is_missing_contact()` — rejects if both `phone` AND `website` are null

**`_is_missing_hours` deliberately excluded from hard rules** — moved to a soft flag, then removed entirely after discovering it was catching all valid listings. Missing hours is common in Google Maps data and does not disqualify a studio.

**`deduplicate()`** — three-pass dedup (phone → address+postal+country → lat/lng within 50m), first-occurrence wins.

**`_write_outputs()`** — writes three CSVs to `data/cleaned/{COUNTRY}/`.

**`run()`** — wires dedup → hard rules → niche verification → output. Niche verification via Crawl4AI is stubbed; listings with a website are tentatively verified, listings without a website are flagged.

---

### 6. Debugging: All CSVs Empty

**Root cause:** 0 listings had a website in the raw data, so all listings went to `flagged`. OutScraper's base search does not reliably populate the `site` field.

**Discovery process:**
- `awk` count of 58 "website" rows was a false positive — it was matching the `street_view_url` column, not `website`
- Confirmed with pandas: `df["website"].notna().sum() == 0`

---

### 7. Added `domains_service` Enrichment to Collect Phase

OutScraper's `google_maps_search` accepts an `enrichment` parameter. Added `domains_service` as the default enrichment so website URLs are populated on every collect run.

**Field mapping fixes in `_normalise_row`** (enriched response uses different field names):

| Old mapping | New mapping |
|-------------|-------------|
| `raw.get("site")` | `raw.get("website") or raw.get("site")` |
| `raw.get("full_address")` | `raw.get("full_address") or raw.get("address")` |
| `raw.get("state")` | `raw.get("state") or raw.get("state_code") or raw.get("us_state")` |

**Added `email` field** — enriched response includes `email_1`. Added to `RawListing` model and `_normalise_row`.

---

### 8. Collect Phase Robustness Improvements

**Incremental CSV writes** — rows are appended to the CSV after each query instead of writing everything at the end. If the run is interrupted, all data collected so far is preserved.

**Timeout per query** — `asyncio.wait_for` wraps each query with a 60s timeout. Slow or failing queries (502s, etc.) are logged and skipped rather than hanging the pipeline.

**`--max-queries` flag** — limits the collect run to the first N queries. Used for sampling before committing to a full run.

**Always start fresh** — the output CSV is deleted at the start of each run to prevent duplicate rows from appended re-runs on the same date.

---

### 9. Sample Run Validation

Ran 3 queries with enrichment enabled to confirm website URLs and emails are captured:

```bash
python pipeline.py --phase collect --country US --max-queries 3
```

Result: 67 rows, **67 with website**, **63 with email** — enrichment working correctly.

---

## Current State

- Collect phase: fully implemented with `domains_service` enrichment, incremental writes, timeout, and sampling flag
- Clean phase: fully implemented (pure Python hard rules + dedup); niche verification via Crawl4AI still stubbed
- Full US re-collect with enrichment is in progress as of end of session

## Files Changed This Session

| File | Change |
|------|--------|
| `pipeline.py` | `load_raw_csv()` implemented; `--max-queries`, `--enrichment` CLI flags added |
| `src/models.py` | `email` field added to `RawListing` |
| `src/agents/cleaner_agent.py` | All stubs implemented |
| `src/tools/outscraper_client.py` | `domains_service` enrichment, incremental writes, timeout, `--max-queries`, field mapping fixes |

---

## Next Steps

1. **Wait for enriched US collect to finish** — confirm website coverage in `data/raw/US/collect_2026-04-04.csv`
2. **Run clean phase against enriched data**
   ```bash
   python pipeline.py --phase clean --country US
   ```
3. **Verify three output CSVs** — check `cleaned` count is meaningful (listings with websites that passed hard rules)
4. **Implement `crawler.py`** (`crawl_website`, `crawl_many`) using Crawl4AI — needed for niche verification
5. **Implement `CleanerAgent` niche verification** — crawl websites, apply keyword heuristics from `context/niche_verification_rules.md`
6. **Repeat collect + clean for CA and AU**
7. **Implement `EnrichmentAgent`** — tool_use loop, field extraction, description generation
