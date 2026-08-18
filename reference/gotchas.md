# Gotchas — mistakes the source site made

Read before sprints 08 and 11. Each of these was found in production code.
They are cheap to avoid up front and annoying to fix later.

## Canonical host drift

`astro.config.mjs` set `site: https://www.example.com` while `robots.txt`
pointed its `Sitemap:` line at the apex `example.com`. Every canonical, every
JSON-LD `@id`, and every hreflang used www; one hand-written file disagreed.

**Rule:** the host appears in exactly one place a human types it —
`astro.config.mjs`. `robots.txt` and any static text file must be generated
from `Astro.site`, or checked by a test. Pick www or apex once and redirect
the other at the CDN.

## Hardcoded absolute paths in build scripts

The OG-image generator did this to avoid adding a dependency:

```js
const APP = '/Users/someone/Projects/other-repo/image-creator-app/';
const require = createRequire(APP);
const puppeteer = require('puppeteer');
```

It worked on one laptop and nowhere else — not on CI, not on a second machine,
not after the sibling repo moved. Saving one devDependency cost portability.

**Rule:** a build script either declares its dependency in `package.json` or
does not exist. If it is not wired into an npm script, it will rot.

## Derived conventions with no enforcement

The OG slug convention (`/services/x/` → `services-x.jpg`) was encoded
independently in three places: a regex in the layout, a `slug` field in a
manifest, and the generator's output filename. Nothing checked they agreed.
Renaming a page silently dropped its social image — no error, no warning.

Contrast with the markdown mirrors, which had `check-mirrors.mjs` as a
`prebuild` gate that failed the build on drift. Same class of problem, one
guarded and one not.

**Rule:** any convention spanning two files gets a build-time check, or gets
collapsed into one file. A code comment is not enforcement.

## One-directional validation

`check-mirrors.mjs` verified that every mirror pointed at a real page. It did
not verify that every page had a mirror. New pages silently shipped with no
markdown twin and no llms.txt entry.

**Rule:** when validating a 1:1 mapping, check both directions.

## Accessibility applied unevenly

The testimonial carousel had `aria-label`, `aria-current`, a play/pause
control, and `aria-live` gating. The three demo panels driven by a shared
cycler hook had none of it — plain `div`s wired with `addEventListener`,
hover-only pause, no keyboard path. Same site, same week, opposite quality.

**Rule:** auto-advancing content needs a pause control (WCAG 2.2.2) and
keyboard-reachable controls. If one component gets it, the shared hook gets
it, so every consumer inherits it.

## Client-side validation mistaken for validation

`submitForm.js` had length caps, a prompt-injection filter, and honeypot
handling — all in the browser, all trivially bypassed by posting directly to
the endpoint. The server-side equivalents existed, but in a repo that was not
version-controlled alongside the site.

**Rule:** client-side checks are UX. Every one of them is duplicated server
side, in a repo you can actually read. If the API lives elsewhere, at minimum
commit its schema next to the site and note where the code lives.

## Dead code left in shipped scripts

```js
const EMAIL = /[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi;   // never used
```

Declared at the top of the email-obfuscation script; the two inline regexes
did the work. Harmless, but it makes the next reader wonder what they missed.

## Schema duplicated across a network boundary

The survey Zod schema existed twice — once in the site, once in the function —
with a comment naming the source of truth and asking future editors to update
both in the same commit. That is a convention, not a mechanism.

**Rule:** publish the schema as a tiny shared package, or generate one file
from the other at build time. If neither is worth it, add a test that imports
both and asserts they produce identical results on a fixture set.
