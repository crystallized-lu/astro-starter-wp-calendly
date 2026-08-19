# Astro Starter (WordPress + Calendly) — START HERE

A sprint-by-sprint build guide for a fast, bilingual Astro site with a
headless WordPress backend and Calendly booking. Extracted from a production
site, not invented.

## How to use this — read this section, then STOP

**Do not read the whole folder.** Every sprint file is self-contained and
costs 2–6k tokens. Reading them all at once costs ~50k and buys nothing,
because each sprint's output changes what the next one should say.

The loop is:

1. Read `START-HERE.md` (this file) — once, at project start.
2. Pick the next sprint from the table below.
3. Open **only** that one file. Build it. Verify it.
4. Close it. Start a fresh context. Go to 2.

If you are an agent: after finishing a sprint, do not open the next file in
the same context window. Report what you did and stop. The human starts the
next sprint.

## Sprint order

Dependencies run top to bottom. 00–03 are load-bearing; everything after is
independently skippable.

| # | File | Builds | Depends on |
|---|------|--------|-----------|
| 00 | `sprints/00-scaffold.md` | Astro + Preact project, config, redirects | — |
| 01 | `sprints/01-tokens-layout.md` | CSS tokens, BaseLayout shell, nav, footer | 00 |
| 02 | `sprints/02-i18n.md` | Bilingual routing, localized slugs, switcher | 01 |
| 03 | `sprints/03-perf-images-fonts.md` | Font strategy, image conventions, hydration tiers | 01 |
| 04 | `sprints/04-seo-jsonld.md` | Meta, canonical, hreflang, entity graph, breadcrumbs | 02 |
| 05 | `sprints/05-aeo-mirrors-llmstxt.md` | Markdown mirrors, build gate, llms.txt | 04 |
| 06 | `sprints/06-blog.md` | Blog fed from WordPress REST API, post layout, RSS, TOC | 01 |
| 07 | `sprints/07-a11y-responsive.md` | Skip link, focus, reduced motion, breakpoints | 01 |
| 08 | `sprints/08-forms-api.md` | Contact form handled by WordPress (CF7 + Flamingo), spam trap | 06 |
| 09 | `sprints/09-booking-calendar.md` | Calendly booking, privacy-respecting link-out or embed | 01 |
| 10 | `sprints/10-privacy-analytics-email.md` | Plausible, no-banner rationale, email obfuscation | 01 |
| 11 | `sprints/11-deploy.md` | Object-storage deploy, gzip, cache policy | 00 |

Minimum viable site: 00, 01, 03, 07, 11. Add the rest as needed.

## Stack — fixed, not configurable

Astro 6 (static) · Preact · WordPress (headless: content + forms) · Scaleway
Object Storage + CDN · Brevo (email/newsletter, optional) · Plausible ·
Calendly. No servers of your own: the only backend is WordPress.

Sprints assume this stack and do not branch. Swapping a layer means editing
that sprint file, which is cheaper than making every file handle every case.

WordPress is the **backend, never the public site**: Astro fetches posts from
its REST API at build time and ships static HTML, and the contact form posts
to a WP form plugin (sprint 08). Visitors never load a WordPress page, so its
performance and most of its attack surface stay out of the picture. Keep the
WP admin on its own (sub)domain, keep it updated, and rebuild the site on
publish — a WP webhook hitting your CI is the usual trigger.

Calendly is a US-based processor. If your visitors are in the EU, name it in
your privacy policy. Sprint 09 shows a link-out pattern that keeps Calendly's
scripts and cookies entirely off your pages, which preserves the no-banner
stance in sprint 10.

## Non-negotiables carried through every sprint

- No personal data in logs, fixtures, or prompts.
- Forms collect the minimum: every field you don't ask for is data you don't hold.
- No cookies without consent — the analytics choice makes consent unnecessary.
- Accessibility is not a later sprint. Sprint 07 is a sweep, not the first pass.
- Trailing slashes always. Canonical host is `www`, everywhere, no exceptions.

## Before going live

Run the bundled security audit skill (`skills/vibe-security-audit/SKILL.md`)
against the finished repo before sprint 11's deploy goes public — it targets
exactly the failure modes AI-assisted builds ship with. Install it to
`~/.claude/skills/` or point Claude at its SKILL.md directly.

## Known gaps in this starter

Read `reference/gotchas.md` before sprint 08 or 11. It lists the things the
source site got wrong, so this build does not repeat them.

Before sprint 11, the human works through `reference/scaleway-setup.md` —
a click-by-click console walkthrough (buckets, API key, CDN, DNS) the AI
cannot do for them. It includes the one safety rule that overrides
everything: secret keys never get pasted into the AI chat.
