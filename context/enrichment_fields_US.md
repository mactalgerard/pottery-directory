# Enrichment Fields — US

_Status: UNVALIDATED — these are starting hypotheses only._
_Run `python pipeline.py --phase research --country US` to validate and overwrite._

---

## About This File

This file defines the enrichment fields to collect for US pottery/ceramics
studio listings. It is read by the EnrichmentAgent before each enrichment run.

It was pre-populated with hypothesised fields from the EnrichedListing model.
The EnrichmentResearcherAgent will validate these against Reddit, Google Maps
review patterns, and local sources — then overwrite this file with confirmed,
market-specific definitions.

---

## Confirmed Fields (Unvalidated)

### class_types
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Core decision factor — what can you actually learn/do here?
- **Values:** list of strings, e.g. `["wheel throwing", "hand building", "glazing"]`
- **Country note:** US searchers commonly mention "wheel throwing" as a top priority

### skill_levels
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Beginners need to know if they're welcome; advanced students want challenges
- **Values:** list of strings, e.g. `["beginner", "intermediate", "advanced"]`

### drop_in_available
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** High-intent signal for casual searchers and tourists
- **Values:** boolean or null

### booking_required
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Helps searchers plan ahead
- **Values:** boolean or null

### price_range
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Key decision factor; US prices vary widely ($15–$150+ per class)
- **Values:** "$" | "$$" | "$$$" — relative to US market

### studio_type
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Community studios offer membership; private studios often more exclusive
- **Values:** "community studio" | "private studio" | "classes only"
- **Country note:** US has a strong community studio culture (e.g. Pottery Northwest model)

### sells_supplies
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Useful for searchers who want to buy supplies locally
- **Values:** boolean or null

### kids_classes
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Common search filter for parents
- **Values:** boolean or null

### private_events
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Birthday parties and bachelorette events are a popular US pottery niche
- **Values:** boolean or null
- **Country note:** "BYOB pottery" events are common at US studios — flag if found

---

## Fields Pending Research Validation

The following may be worth adding for US specifically — to be confirmed:

- `firing_services` — Does the studio offer kiln firing for outside work?
- `byob_events` — BYOB pottery nights (common in US)
- `membership_available` — Monthly/annual open studio memberships
- `gift_cards` — Gift cards available (popular for US gifting searches)
