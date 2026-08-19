# Build your own website — with an AI assistant doing the coding

This is a **recipe book for building a professional website**, written for AI
coding assistants like Claude Code. You don't need to know how to code. You
tell your AI assistant to follow this guide, and it builds the site step by
step while you make the decisions that matter: what the site says, how it
looks, what it's called.

The result is not a toy. Sites built from this guide load in under a second,
work in two languages, rank well on Google, are readable by AI search engines
like ChatGPT and Perplexity, and meet accessibility standards — the things
professional agencies charge real money for.

## What you'll end up with

- A **fast, modern website** for your business, project, or idea
- A **blog you write in WordPress** — a familiar editor, no code involved.
  WordPress stays behind the scenes; visitors only ever see the fast site.
- A **"book a call" button** powered by Calendly
- A **contact form** that emails you when someone writes
- A site that looks good on phones, works for people with disabilities, and
  doesn't need a cookie banner

## What you need

1. **An AI coding assistant** — this guide is written for
   [Claude Code](https://claude.com/claude-code), but any capable coding
   agent can follow it
2. **A couple of hours at a time**, over a week or two — the guide is split
   into 12 small stages ("sprints"), and you do one sitting per stage
3. **Accounts** you'll create along the way: WordPress (for writing),
   Calendly (for bookings), and a hosting provider — the guide walks
   through each when it's needed

## How to use it

1. Download this folder (green **Code** button above → *Download ZIP*).
2. Open your AI assistant in that folder and say:
   > Read START-HERE.md and tell me which sprints my project needs.
3. It will ask you a few questions (Do you want a blog? Two languages?),
   then build one sprint at a time. After each sprint it stops, shows you
   what it did, and you check that you like it before moving on.

That stop-and-check rhythm is deliberate. You stay in charge; the AI never
runs ahead and builds an hour of things you didn't want.

## Before your site goes public: the safety check

AI-built projects tend to share the same blind spots — things that work fine
in normal use but leave a door open for someone malicious. This folder
includes a **security check-up** (`skills/vibe-security-audit/`) that your AI
assistant runs before launch. When you reach the final sprint, say:

> Before we deploy, run the security audit in skills/vibe-security-audit
> and walk me through anything it finds.

It also lives in its own repository:
[dress-to-impress](https://github.com/crystallized-lu/dress-to-impress).

## For technical readers

Astro 6 (fully static) + Preact islands · headless WordPress via REST at
build time · Calendly by link-out (no third-party scripts on-page) · contact
form via CF7's REST endpoint (Flamingo storage, no custom backend) ·
object-storage hosting behind a CDN. The sprints
are docs, not scaffolding: each is a self-contained 2–6k-token file with the
patterns, the traps, and verify steps. Start at [START-HERE.md](START-HERE.md);
agents get [SKILL.md](SKILL.md). Extracted from a production site, not
invented.
