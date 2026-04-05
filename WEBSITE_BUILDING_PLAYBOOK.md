# Website Building Playbook
### Pottery & Ceramics Classes Directory

> Synthesised from the Ship Your Directory *Directory Journal* — Stages 4 (Building), 5 (SEO), 6 (Growing), and 7 (Monetizing).
> Use this as context when building the pottery and ceramics directory website.

---

## Overview

The recommended build path is: **Claude Code + Next.js + Supabase + Vercel**. This is Frey Chu's primary stack and the one the entire Journal is built around. It is faster, more flexible, and comparable in cost to a premium WordPress setup once you factor in themes and plugins.

The journey from zero to live breaks into five phases:
1. Set up accounts and development environment
2. Build the local dev server (first draft)
3. Import real data and iterate
4. On-page SEO pass
5. Deploy and go live

---

## 1. Tech Stack & Tooling

### Core Stack

| Tool | Role | Cost | Link |
|---|---|---|---|
| **Claude Code** | Primary build tool — generates, iterates, and maintains all code | From $17/month | claude.ai |
| **Next.js** | Web framework — the foundation the directory is built on | Free | nodejs.org |
| **Node.js** | Required to run Next.js projects locally | Free | nodejs.org |
| **Cursor** | Code editor (Frey's preference; VS Code or any editor works) | Free | cursor.com |
| **GitHub** | Version control — create a repo for the project | Free | github.com |
| **Vercel** | Hosting — deploy and go live. Generous free tier. | Free tier | vercel.com |
| **Supabase** | Database — stores all listing data; manageable via UI or MCP | Free tier | supabase.com |
| **Supabase MCP** | Lets Claude Code communicate directly with Supabase | Included | — |

### Why Claude Code over WordPress

Frey's direct comparison: "You can build extremely high-quality directories with advanced features that WordPress frankly can't do. You can also scrape, clean, and enrich data all within Claude Code. It handles the full pipeline." The price is comparable to or cheaper than WordPress once you add premium themes and paid plugins.

### Essential Setup (Do These Before Writing Any Code)

1. **Install Node.js** from nodejs.org — required to create Next.js projects
2. **Install Cursor** (or VS Code) as your code editor
3. **Create a GitHub account** and a new repository for the project
4. **Create a Vercel account** — this is where the site gets hosted and deployed
5. **Create a Supabase account** — this is where all listing data lives
6. **Purchase and install Claude Code** (from $17/month)
7. **Install the Supabase MCP** — without this, Claude Code cannot interact with the database
8. **Set up Git commits** from inside Claude Code — essential for version control and rollbacks. "You will break things, and you'll want to undo them."

Frey's note on getting started: "If you're just getting started with vibe coding, it can be a little challenging with a steep learning curve in the very beginning, but it's 100% worth it. You can create anything you can imagine with Claude Code."

Video walkthroughs:
- Non-coder setup guide: https://www.youtube.com/watch?v=A-0qjpViZFQ&t=525s
- Coding with Claude Code: https://www.youtube.com/watch?v=s-YOKU74BXU&t=5s

---

## 2. Site Architecture

### Page Hierarchy (Nationwide Directory)

```
/                                              ← Homepage (search bar + featured listings)
/potteryandceramicsclasses/                    ← Category root (optional)
/potteryandceramicsclasses/[state]/            ← State-level pages (e.g. /california/)
/potteryandceramicsclasses/[state]/[city]/     ← City-level pages (e.g. /california/los-angeles/)
/potteryandceramicsclasses/[state]/[city]/[listing-slug]/   ← Individual listing pages
```

This URL structure is directly taken from Frey's example in the Journal:
> `yourdomain.com/potteryandceramicsclasses/california/los-angeles/platinum-portables`

### Page Types and Their Purpose

**Homepage**
- Contains a dynamic search bar where users type their city or zip code and see all listings in that area. Frey calls this "one of the most impactful features for user experience."
- Links to state pages and popular city pages

**State pages**
- Dedicated page for every US state with listings
- H1 = "Pottery and Ceramics Classes [State]"
- Links to all city pages within that state

**City pages**
- Dedicated page for every city that has listings
- H1 = "Pottery and Ceramics Classes [City]" (e.g. "Pottery and Ceramics Classes Los Angeles")
- Lists all local listings with brief summaries and links through to individual listing pages

**Individual listing pages**
- The most important page type — "every other page exists to get people here"
- Must include a lead capture form (see Section 3)
- Links back up to city and state pages (breadcrumbs)

**Supporting pages**
- User authentication pages (sign up / log in)
- User dashboard (for businesses to manage their listing, users to save favourites)
- About, Contact, Privacy Policy, Terms of Service

### Initial Prompt for Claude Code

Use this as your starting context when initialising the build. Adapt as needed:

> *"I'm creating a Pottery and ceramics classes directory. The goal is to allow people looking for Pottery and ceramics classes to easily find businesses near them. This is going to be a nationwide directory, so I would like dedicated state location pages, city-level location pages, and individual listings. I would like to create this using the best SEO practices. The goal is to SEO optimize it and generate leads that I can sell to businesses, so we need a way to capture leads on every listing page."*

Three questions to answer in your brain dump before prompting:
- What kind of directory? Nationwide, state-specific, or city-specific?
- How does this help your future website visitors?
- How do you plan to monetize it?

---

## 3. Listing Page Structure

### Required Fields to Display

Pull these from your Supabase database (populated during Stage 3: Data Curation):

| Field | Display Format | Notes |
|---|---|---|
| `name` | H1 or prominent heading | Business name |
| `address` | Formatted address block | Full street address |
| `city` + `state` + `postal_code` | Combined in address block | — |
| `phone` | Clickable `tel:` link | Phone number |
| `website` | Clickable external link | Opens in new tab |
| `working_hours` | Formatted hours table | Store hours by day |
| `business_status` | Open/closed badge | Drive trust |
| `reviews` | Review count with star display | Google review count |
| `latitude` + `longitude` | Embedded map | Google Maps embed |
| `street_view` | Image | Optional but adds credibility |

Plus all niche-specific enrichment fields identified during Data Curation (e.g. class types offered, skill levels accepted, price range, booking required, wheelchair accessible, etc.).

### Lead Capture Form (Critical)

Every listing page must have a lead submission form. This is the primary monetisation mechanism for a lead-gen directory model.

When someone submits the form, the lead should be emailed directly to you (and/or to the business). Claude Code can wire this up during the build phase.

Prompt example: *"Design your listing page with a lead form. Your listing page is the most important page on your site. Every other page exists to get people here. Make sure it has a lead submission form so you can start collecting leads."*

### Additional Listing Page Features

- **Breadcrumb navigation**: e.g. Home > California > Los Angeles > [Business Name]
- **Back-links to city and state pages**: explicit text links, not just breadcrumbs
- **User reviews section**: requires user authentication (see below)

### Iterative Design Workflow (Frey's Personal Method)

1. Screenshot what Claude Code built
2. Paste the screenshot into Claude Chat
3. Say: *"I want to redesign this page to look more modern and clean with these specific colours"*
4. Claude Chat generates an interactive artifact you can preview and click through
5. Once the design looks right, bring it back to Claude Code to build for real

"It's much nicer to build the right thing once rather than rebuilding multiple times."

### User Authentication & Dashboard

These are listed under "Continue improving your directory" — build them after the core listing pages are working:

- **User auth**: Login and account creation so people can claim listings, leave reviews, post comments
- **User dashboard**: When people log in, businesses can manage their listing; users can save favourites or track submissions

---

## 4. SEO Foundations

### On-Page SEO (Apply Before Launch)

#### H1 Tags
- Homepage H1: contains the main keyword (e.g. "Pottery and Ceramics Classes Near Me")
- City pages H1: keyword + city (e.g. "Pottery and Ceramics Classes Los Angeles")
- State pages H1: keyword + state (e.g. "Pottery and Ceramics Classes in California")
- Listing pages H1: business name
- Every page must have **exactly one H1**

#### URL Structure
URLs should be self-describing — reading the path alone should tell you exactly what the page is about.

Pattern: `yourdomain.com/[keyword]/[state]/[city]/[listing-slug]`
Example: `yourdomain.com/potteryandceramicsclasses/california/los-angeles/platinum-portables`

#### Meta Titles & Descriptions
- Every page needs a meta title containing the target keyword
- Every page needs a meta description containing the target keyword
- These must be set for every page type: homepage, state, city, and listing pages

#### Image Alt Text
- Every image needs alt text with the target keyword where relevant

#### Internal Linking
- Every listing page links back to its city page and state page
- Breadcrumbs on every listing page
- City pages link to all listings and to the parent state page
- State pages link to all city pages within them

### Technical SEO (Apply After Build Is Mostly Done)

Run both of these Claude Code audit prompts before going live:

**Audit prompt 1 — General SEO:**
> *"Do a thorough audit. Look at every web page I've created and activate your expert SEO lens. Tell me if there are any improvements, including technical SEO like schema markup and robots.txt. Anything that would help get this indexed by Google, let me know."*

**Audit prompt 2 — Indexation:**
> *"From an indexation and SEO perspective, check for any issues I might have missed. Thin content, broken pages, redirects, missing sitemaps. Do a thorough check and let me know what to fix."*

Key technical items these prompts will surface:
- Schema markup (structured data for local businesses)
- robots.txt configuration
- XML sitemap generation
- Thin content pages
- Broken links / 404s
- Redirect chains

### Post-Launch SEO Setup

| Task | Tool | When |
|---|---|---|
| Verify domain | Google Search Console (free) | Day 1 after launch |
| Generate and submit sitemap | Claude Code → Search Console | Day 1 after launch |
| Add tracking code | Google Analytics (free) | Day 1 after launch |
| Verify Analytics is firing | GA Real-Time report | Day 1 after launch |
| Run full site audit | Ahrefs Webmaster Tools (free) | Week 1 after launch |
| Fix issues from audit | Export list → Claude Code | Week 1–2 after launch |
| Check Coverage report | Google Search Console | After 3–5 days |
| Start building backlinks | Manual outreach | 2–3 weeks after launch |

**Verifying Analytics works**: Visit your site and check the Real-Time report in Google Analytics — you should see yourself as an active user.

**Ahrefs Webmaster Tools**: Connect via Google Search Console and it runs a full audit flagging broken links, missing meta tags, slow pages, orphan pages, and redirect chains. Export the list and feed it directly to Claude Code to fix.

### Backlink Strategy (Post-Launch Priority)

Frey: *"If you learn how to build backlinks consistently, you are now better than 90% of all SEOs in the world... Backlinks are the unlock."*

Wait 2–3 weeks after launch before actively building backlinks. Check Search Console first — if you're already ranking for branded and city-specific terms within a month, your on-page SEO is working.

**Preferred strategy — link swaps:**
1. Find a competing directory
2. Look it up in Ahrefs
3. Check its backlinks (who links to it)
4. Reach out to those websites
5. Offer ~$50 to swap your link in place of your competitor's

Full backlink video: https://www.youtube.com/watch?v=Vj1LUdq4nDY&t=40s

---

## 5. Going Live Checklist

Work through these in order. Do not go live until every item is checked.

### Build Readiness
- [ ] Next.js project initialised and running locally
- [ ] Supabase database created and connected via MCP
- [ ] GitHub repo created; commits working from Claude Code
- [ ] Homepage with dynamic city/zip search bar built
- [ ] State pages generated for all states with listings
- [ ] City pages generated for all cities with listings
- [ ] Individual listing pages built with all data fields displaying correctly
- [ ] Lead capture form on every listing page (submissions emailed to you)
- [ ] Breadcrumb navigation on all listing and city pages
- [ ] User authentication pages built (optional but recommended before launch)

### Data
- [ ] Real listing data loaded into Supabase (not dummy data)
- [ ] Addresses, phone numbers, and hours formatted correctly
- [ ] No closed or permanently shut businesses in the dataset
- [ ] All listings have at minimum: name, address, phone, website, hours

### On-Page SEO
- [ ] Every page has exactly one H1 with the correct keyword pattern
- [ ] Meta titles set on all page types (homepage, state, city, listing)
- [ ] Meta descriptions set on all page types
- [ ] Image alt text added throughout
- [ ] URL slugs follow the keyword/state/city/listing-name pattern
- [ ] Internal links: listings → city pages → state pages → homepage
- [ ] Breadcrumbs on all listing pages
- [ ] Both Claude Code SEO audit prompts run and issues resolved
- [ ] Schema markup applied (local business schema on listing pages)
- [ ] robots.txt configured correctly
- [ ] XML sitemap generated

### Deployment
- [ ] Domain purchased (aim to include niche keyword in domain if possible)
- [ ] Domain registered through Vercel or connected to Vercel
- [ ] Site deployed to Vercel and live on the custom domain
- [ ] All pages loading correctly on live domain
- [ ] Google Search Console: domain verified + sitemap submitted
- [ ] Google Analytics: tracking code live + Real-Time report confirming data

---

## 6. Monetisation Setup

### The Fundamental Rule: Don't Monetise Too Early

Frey's direct instruction: *"A lot of people force monetization too early."*

Monetisation readiness depends on the model you're running.

### Model 1 — Display Ads

**Trigger**: Traffic volume — you need to hit a threshold of monthly visitors before ad networks will accept you.

**How it works**: Sign up for an ad network once you meet their minimum traffic requirement.

| Network | Notes |
|---|---|
| **Google AdSense** | Lower traffic threshold; good starting point |
| **Mediavine** | Higher quality ads; requires ~50,000 sessions/month |

**When to apply**: Once you're consistently hitting the traffic threshold for your chosen network. Do not add ad code speculatively — focus on SEO and traffic first.

### Model 2 — Lead Generation

**Trigger**: Lead quality and frequency — not raw traffic.

The questions to track:
- Are the leads high quality?
- How frequently are they coming in?
- How valuable are they to the businesses receiving them?

**How it works**: The lead capture form on every listing page is the foundation. Once leads are coming in consistently, you approach businesses and sell the leads, offer featured/claimed listings, or charge a monthly subscription for lead delivery.

**When to activate**: The lead form should be live from day one (it's part of the going-live checklist). But you don't need to approach businesses for payment until you can demonstrate lead volume and quality.

### Building in Preparation for Both Models

The lead form is already baked into the listing page structure (see Section 3). For display ads, no special prep is needed beyond building traffic. The user dashboard (where businesses can manage claimed listings) is the natural upsell path once leads are flowing.

---

## Quick Reference: Recommended Claude Code Prompts

| Purpose | Prompt |
|---|---|
| Initial project setup | *"I'm creating a Pottery and ceramics classes directory... nationwide directory... dedicated state location pages, city-level location pages, and individual listings... best SEO practices... generate leads that I can sell to businesses... lead submission form on every listing page."* |
| Load CSV data | *"Here is all the data for my directory. Create the database tables for it and populate the listings from this data."* |
| Add Analytics | *"Add Google Analytics to my project"* + your tracking ID |
| Generate sitemap | *"Generate a sitemap for my project and give me the sitemap URL."* |
| SEO audit | *"Do a thorough audit. Look at every web page I've created and activate your expert SEO lens. Tell me if there are any improvements, including technical SEO like schema markup and robots.txt."* |
| Indexation audit | *"From an indexation and SEO perspective, check for any issues I might have missed. Thin content, broken pages, redirects, missing sitemaps. Do a thorough check."* |
| Fix Ahrefs issues | *"Here are all the technical SEO issues on my website. Can you go through and fix them?"* + paste Ahrefs export |
| Go live | *"I want to go live"* + follow the Vercel deployment steps it gives you |
