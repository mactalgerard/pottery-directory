# Enrichment Fields — CA

_Aligned with US-validated fields on 2026-04-06_
_Status: VALIDATED (uniform schema across all countries — see CLAUDE.md for rationale)_

## Decision Note

The CA enrichment fields are kept identical to the US-validated set. Country-specific
hypothetical fields (`bilingual_classes`, `indigenous_clay_practices`, `bipoc_led`) were
evaluated and deemed too narrow in coverage (<5% of listings) to justify schema divergence.
The 14 US-validated fields apply equally to Canadian pottery studios.

Currency convention: **CAD**. Price range tiers ($ | $$ | $$$) use the same relative scale
as US — CA studio pricing is broadly comparable to the US in CAD terms (~$35–$65 CAD for
one-off workshops, $100–$200 CAD/month for memberships).

---

## Confirmed Fields

### `class_types`
- **Confirmed:** yes
- **Country note:** CA studios use the same terminology as US (wheel throwing, hand building,
  glazing, sculpting). Both English and French terminology may appear in Quebec listings
  ("poterie," "céramique") but English field values are used throughout.

### `skill_levels`
- **Confirmed:** yes
- **Country note:** Same beginner/intermediate/advanced gate as US. Many CA studios require
  completing an introductory course before granting open studio or membership access.

### `drop_in_available`
- **Confirmed:** yes
- **Country note:** Drop-in availability varies by studio. Pre-booking is common in major
  CA cities (Toronto, Vancouver, Montreal).

### `booking_required`
- **Confirmed:** yes
- **Country note:** None.

### `price_range`
- **Confirmed:** yes
- **Country note:** Currency is CAD. Single workshops typically $35–$65 CAD; memberships
  $100–$200 CAD/month. Firing fees often charged separately.
  $ = budget (under $50/session), $$ = mid-range ($50–$90), $$$ = premium ($90+).

### `studio_type`
- **Confirmed:** yes
- **Country note:** Same community/private/classes-only/membership distinction as US applies
  in CA. Non-profit community studios and arts centres are common in CA cities.

### `sells_supplies`
- **Confirmed:** yes
- **Country note:** Clay and glazes available for purchase at many CA studios. Some studios
  stock Canadian-sourced clay bodies.

### `kids_classes`
- **Confirmed:** yes
- **Country note:** Kids programs and family workshops are widely offered at CA community
  studios. School break programs (March break, summer) are common formats.

### `private_events`
- **Confirmed:** yes
- **Country note:** Bachelorette parties, corporate team building, and birthday parties are
  all common CA private event formats. Similar to US.

### `open_studio_access`
- **Confirmed:** yes
- **Country note:** "Open studio," "studio membership," and "studio access" terminology is
  identical to US. This remains the #1 differentiator for ongoing potters in CA.

### `firing_services`
- **Confirmed:** yes
- **Country note:** Kiln firing for home potters is available at many CA studios, especially
  in cities with large ceramics communities (Toronto, Vancouver).

### `byob_events`
- **Confirmed:** yes
- **Country note:** "Sip & Throw," "Pottery & Prosecco," and similar social formats exist
  in CA. Liquor laws vary by province — some studios are licensed rather than BYOB.

### `date_night`
- **Confirmed:** yes
- **Country note:** Couples pottery sessions are marketed in CA similarly to US. Common
  in major urban areas alongside bachelorette and corporate events.

### `membership_model`
- **Confirmed:** yes
- **Country note:** Monthly studio memberships with tiered access are standard in major CA
  cities. Structure mirrors US (monthly unlimited, class packs, firing-only).

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
