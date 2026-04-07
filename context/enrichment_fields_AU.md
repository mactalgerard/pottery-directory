# Enrichment Fields — AU

_Aligned with US-validated fields on 2026-04-06_
_Status: VALIDATED (uniform schema across all countries — see CLAUDE.md for rationale)_

## Decision Note

The AU enrichment fields are kept identical to the US-validated set. Country-specific
hypothetical fields (`ndis_accessible`, `regional_network`, `indigenous_pottery`) were
evaluated and deemed too narrow in coverage (<5% of listings) to justify schema divergence.
The 14 US-validated fields apply equally to Australian pottery studios.

Currency convention: **AUD**. Price range tiers ($ | $$ | $$$) use the same relative scale
as US — AU studio pricing is broadly comparable (~$30–$60 AUD for one-off workshops,
$100–$200 AUD/month for memberships).

---

## Confirmed Fields

### `class_types`
- **Confirmed:** yes
- **Country note:** AU studios commonly use "hand building" and "clay classes" terminology
  alongside "wheel throwing." Search terms in AU favour "clay classes" and "ceramics classes"
  over "pottery classes."

### `skill_levels`
- **Confirmed:** yes
- **Country note:** Same beginner/intermediate/advanced gate as US. Many AU studios require
  completing an introductory course before granting open studio or membership access.

### `drop_in_available`
- **Confirmed:** yes
- **Country note:** Drop-in availability varies by studio. Pre-booking via online booking
  systems is common in AU metropolitan areas (Sydney, Melbourne, Brisbane).

### `booking_required`
- **Confirmed:** yes
- **Country note:** None.

### `price_range`
- **Confirmed:** yes
- **Country note:** Currency is AUD. Single workshops typically $30–$60 AUD; memberships
  $100–$200 AUD/month. Firing fees charged separately at many studios.
  $ = budget (under $45/session), $$ = mid-range ($45–$80), $$$ = premium ($80+).

### `studio_type`
- **Confirmed:** yes
- **Country note:** Same community/private/classes-only/membership distinction as US applies
  in AU. "Community studio" and "ceramics collective" are common AU terms.

### `supplies_available`
- **Confirmed:** yes (field name: `sells_supplies` in model, maps to `supplies_available` concept)
- **Country note:** Clay available for purchase at most studios. Some AU studios stock
  local/regional clay bodies alongside imported options.

### `kids_classes`
- **Confirmed:** yes
- **Country note:** "School holiday programs" are an AU-specific format (classes run during
  term breaks). Worth capturing under kids_classes.

### `private_events`
- **Confirmed:** yes
- **Country note:** Hen's nights (AU equivalent of bachelorette parties), corporate team
  building, and birthday parties are all common AU private event formats.

### `open_studio_access`
- **Confirmed:** yes
- **Country note:** "Open studio," "studio membership," and "studio access" are used in AU
  as they are in the US. This remains the #1 differentiator for ongoing potters.

### `firing_services`
- **Confirmed:** yes
- **Country note:** Kiln firing for home potters is available at many AU studios, though
  less prominently marketed than in the US.

### `byob_events`
- **Confirmed:** yes
- **Country note:** "Sip & Throw," "Wheel and Wine," and "Clay + Drinks" are common
  AU equivalents of US "Sip & Spin" events. BYO is widely accepted in AU social contexts.

### `date_night`
- **Confirmed:** yes
- **Country note:** Couples pottery sessions are marketed in AU similarly to US, often
  listed alongside hens nights and social events.

### `membership_model`
- **Confirmed:** yes
- **Country note:** Monthly studio memberships with tiered access are common in major AU
  cities. Structure is similar to US (monthly unlimited, class packs, firing-only).

---

## Summary Table

| Field | Status | Priority |
|---|---|---|
| `class_types` | ✅ Confirmed | High |
| `skill_levels` | ✅ Confirmed | High |
| `drop_in_available` | ✅ Confirmed | High |
| `booking_required` | ✅ Confirmed | Medium |
| `price_range` | ✅ Confirmed | High |
| `studio_type` | ✅ Confirmed | High |
| `sells_supplies` | ✅ Confirmed | Medium |
| `kids_classes` | ✅ Confirmed | Medium |
| `private_events` | ✅ Confirmed | High |
| `open_studio_access` | ✅ Confirmed | **Critical** |
| `firing_services` | ✅ Confirmed | High |
| `byob_events` | ✅ Confirmed | High |
| `date_night` | ✅ Confirmed | Medium |
| `membership_model` | ✅ Confirmed | High |
