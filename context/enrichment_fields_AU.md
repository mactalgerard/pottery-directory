# Enrichment Fields — AU

_Status: UNVALIDATED — these are starting hypotheses only._
_Run `python pipeline.py --phase research --country AU` to validate and overwrite._

---

## About This File

This file defines the enrichment fields to collect for Australian pottery/ceramics
studio listings. It is read by the EnrichmentAgent before each enrichment run.

It was pre-populated with hypothesised fields from the EnrichedListing model.
The EnrichmentResearcherAgent will validate these against Reddit, Google Maps
review patterns, and Australian-specific sources — then overwrite this file.

**Important AU terminology note:** Australian studios more commonly use "hand
building" and "clay classes" than "pottery wheel". The researcher agent should
use AU-appropriate search terms when validating fields.

---

## Confirmed Fields (Unvalidated)

### class_types
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Core decision factor — what can you actually learn/do here?
- **Values:** list of strings, e.g. `["wheel throwing", "hand building", "glazing"]`
- **Country note:** "clay classes" and "hand building" are primary AU search terms;
  "wheel throwing" is understood but less dominant than in US

### skill_levels
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Beginners need to know if they're welcome; advanced students want challenges
- **Values:** list of strings, e.g. `["beginner", "intermediate", "advanced"]`

### drop_in_available
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** High-intent signal for casual searchers
- **Values:** boolean or null

### booking_required
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Helps searchers plan ahead
- **Values:** boolean or null

### price_range
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Key decision factor; values are AUD-relative
- **Values:** "$" | "$$" | "$$$" — relative to Australian market prices
- **Country note:** Price thresholds differ from US — researcher should define AUD brackets

### studio_type
- **Status:** Hypothesised
- **Signal source:** General pottery knowledge
- **Rationale:** Community studios offer membership; private studios often more exclusive
- **Values:** "community studio" | "private studio" | "classes only"

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
- **Rationale:** Birthday parties and team events
- **Values:** boolean or null

---

## Australia-Specific Fields (Pending Research Validation)

The following may be worth adding for AU specifically:

- `ndis_accessible` — Studio is NDIS-registered or explicitly accessible to
  participants with disability (significant in AU context)
- `regional_network` — Studio is part of a regional ceramics network or guild
- `indigenous_pottery` — Studio incorporates or teaches Aboriginal and Torres Strait
  Islander ceramic traditions
- `membership_available` — Monthly/annual open studio memberships
