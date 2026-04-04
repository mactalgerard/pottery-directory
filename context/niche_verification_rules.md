# Niche Verification Rules

Rules for determining whether a Google Maps listing qualifies as a legitimate
pottery or ceramics studio for inclusion in this directory.

---

## Automatic Pass (include without review)

A listing passes if the business clearly:
- Offers pottery or ceramics classes (wheel throwing, hand building, glazing, etc.)
- Provides open studio access or studio memberships
- Operates as a community ceramics studio (even if it also sells supplies)

---

## Automatic Rejection (hard rules — no human review needed)

Reject immediately if:

| Rule | Signal |
|------|--------|
| Business is closed | `business_status` = "temporarily closed" or "permanently closed" |
| No working hours | `working_hours` is null or empty |
| Incomplete address | `full_address` is null AND (`city` or `postal_code` is missing) |
| No contact method | `phone` AND `website` are both null/empty |
| Clearly unrelated business | Website content is a restaurant, clothing store, real estate agency, etc. |
| General craft retailer | Michaels, Hobby Lobby, or equivalent — sells craft supplies broadly, no pottery focus |

---

## Flag for Human Review (do not auto-reject)

Flag these cases — a human reviewer must make the final call:

| Case | Signal |
|------|--------|
| Pottery supply retailer | Sells clay, wheels, kilns — but no evidence of studio access or classes |
| Gallery with incidental workshops | Art gallery that occasionally runs a one-off ceramics workshop |
| Website unavailable | Business has a website URL but the crawl failed or returned < 200 chars |
| No website | Phone-only listing — cannot verify niche remotely |
| Ambiguous business name | Name doesn't indicate pottery (e.g. "The Creative Space") and website is thin |

---

## Keyword Signals (for Crawl4AI niche detection)

### Positive (confirms pottery/ceramics niche)
- pottery, ceramics, clay, ceramic
- wheel throwing, hand building, hand-building
- kiln, glazing, glaze
- studio membership, open studio, studio access
- clay classes, pottery classes, ceramics classes
- beginner pottery, intro to ceramics

### Supply-only signals (flag, do not auto-pass)
- pottery supplies, clay supplies
- kiln for sale, pottery wheels for sale
- "we sell" + (clay / glazes / tools) without class language

### Negative (confirm rejection)
- "art supplies" as primary offering
- No mention of pottery, ceramics, clay, or kiln anywhere on homepage
- Clear evidence of an unrelated primary business

---

## Country-Specific Notes

### AU
- "clay classes" is often used instead of "pottery classes" — treat as equivalent
- "hand building" is more common than "hand-building" — both are valid signals
- Look for "NDIS" as an accessibility indicator (not a rejection signal)

### CA
- "atelier de poterie" or "cours de céramique" = pottery studio in French — valid
- Bilingual listings (EN + FR) are common in Quebec — do not reject for language

### US
- "BYOB pottery" events often hosted at studios — valid positive signal
- "paint-your-own pottery" (e.g. Color Me Mine) — **flag**, not a throwing/building studio
