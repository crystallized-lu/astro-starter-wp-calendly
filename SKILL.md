---
name: astro-wordpress-starter
description: Use when building a new marketing or consultancy website that needs speed, bilingual content, SEO/AEO, a WordPress-backed blog, accessibility, WordPress-handled forms, and Calendly booking. Also use when the user mentions "new website", "site framework", "Astro starter", "headless WordPress", "bilingual site", or "llms.txt". Delivers a sprint-by-sprint build plan, not a code dump.
---

# Astro Starter — WordPress backend, Calendly booking

A staged build guide for an Astro site with: sub-second loads, EN/FR from day
one, SEO + answer-engine optimization, a blog fed from headless WordPress,
WCAG AA, a WordPress-handled contact form, and Calendly booking.

## How to use

Read `START-HERE.md`. It contains the sprint table and the context-budget
rules. Then open exactly one sprint file at a time from `sprints/`.

**Do not read multiple sprint files in one context.** They are sized to be
read alone. The whole folder is ~50k tokens; a single sprint is 2–6k.

## When this applies

Greenfield sites, or a rebuild where the current stack is being replaced.
Not for small edits to an existing site — those need the repo, not this.

## First question to ask

Which sprints does this project actually need? Most need 00, 01, 03, 07, 11.
Bilingual, blog, forms, and booking are all optional and independent. Confirm
scope before starting sprint 00, because `astro.config.mjs` and the layout
shell differ depending on whether i18n is in scope.
