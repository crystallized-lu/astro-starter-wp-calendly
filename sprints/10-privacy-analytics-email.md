# Sprint 10 — Privacy, analytics, email obfuscation

**Read only this file.** ~3k tokens. Requires sprint 01.

## Goal

Analytics with no cookie banner (because none is needed), email addresses
that survive scraping, and a content-security policy.

## Analytics — cookieless by design

```astro
{!noAnalytics && (
  <>
    <link rel="preconnect" href="https://plausible.io" />
    <link rel="dns-prefetch" href="https://plausible.io" />
  </>
)}
```

```astro
{!noAnalytics && (
  <>
    <script async src="https://plausible.io/js/script.js" data-domain="example.com"></script>
  </>
)}
```

**There is no cookie banner and that is the point.** Plausible sets no
cookies and stores no personal data, so ePrivacy Art. 5(3) consent does not
apply. The banner is not omitted through oversight — it is unnecessary
because of the analytics choice. Document that reasoning somewhere durable;
someone will ask, probably during a client security review.

If you swap in anything that sets a cookie or fingerprints, you inherit the
banner, the consent-state storage, and the gating logic. That is the real
cost of the alternative.

The `noAnalytics` prop exists for pages making a stricter promise — a survey
claiming "no tracking on this page" needs that to be literally true.

### Subresource integrity

This is the only third-party script on the site, and it executes with full
page privileges. Normally that calls for `integrity="sha384-…"` plus
`crossorigin="anonymous"`, so a compromised CDN cannot swap it.

You cannot pin it here: Plausible updates `script.js` in place, and a hash
would break the moment they ship. Two options, in order of preference:

1. **Self-host the script**, refreshed on a schedule. You control the bytes,
   SRI becomes possible, and the `preconnect` disappears too.
2. **Keep the CDN copy** and rely on the CSP `script-src` allowlist to limit
   the blast radius to that one origin.

Any *other* external script you add — a widget, a font loader, an embed —
gets SRI, no exceptions. Analytics is the one justified exception, and only
because option 1 stays open.

The only client-side persistence should be non-tracking UI state:

```js
localStorage.getItem('banner-dismissed')
```

One key, no identifier, no consent needed.

## Email obfuscation — postbuild, no JavaScript

Encode `mailto:` targets and visible addresses as hex HTML entities. The
parser decodes them natively in both attribute and text contexts, so links
work with JavaScript disabled, while a naive scraper regex finds no `@`.

`scripts/obfuscate-emails.mjs`, wired as `postbuild`:

```js
// Entity-encode emails in built HTML so scraper regexes miss them, while
// browsers still render and link them with NO JavaScript. The self-hosted
// equivalent of a CDN's email obfuscation feature.
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'dist';

const encode = (s) => [...s].map((c) => `&#x${c.codePointAt(0).toString(16)};`).join('');

// Narrow scope on purpose: mailto: hrefs and anchor text only. Both contexts
// are impossible inside a JSON string, so JSON-LD is untouched without
// needing to parse the HTML.
function rewrite(html) {
  let n = 0;
  const out = html
    .replace(/mailto:([\w.+-]+@[\w.-]+\.[a-z]{2,})/gi, (_, e) => (n++, `mailto:${encode(e)}`))
    .replace(/>(\s*)([\w.+-]+@[\w.-]+\.[a-z]{2,})(\s*)</gi, (_, a, e, b) => (n++, `>${a}${encode(e)}${b}<`));
  return { out, n };
}

function walk(dir) {
  return readdirSync(dir, { recursive: true })
    .filter((f) => f.endsWith('.html'))
    .map((f) => join(dir, f));
}

if (process.argv.includes('--test')) {
  const src = `<a href="mailto:x@y.io">x@y.io</a> <script type="application/ld+json">{"email":"x@y.io"}</script>`;
  const { out, n } = rewrite(src);
  console.assert(n === 2, `expected 2 rewrites, got ${n}`);
  console.assert(!/mailto:x@y\.io/.test(out), 'mailto not encoded');
  console.assert(!/>x@y\.io</.test(out), 'anchor text not encoded');
  console.assert(out.includes(`"email":"x@y.io"`), 'JSON-LD email was wrongly touched');
  console.assert(out.includes('&#x40;'), '@ not entity-encoded');
  console.log('self-test ok');
  process.exit(0);
}

let files = 0, total = 0;
for (const path of walk(DIST)) {
  const { out, n } = rewrite(readFileSync(path, 'utf8'));
  if (n) { writeFileSync(path, out); files++; total += n; }
}
console.log(`obfuscate-emails: encoded ${total} address(es) across ${files} file(s)`);
```

```json
"postbuild": "node scripts/obfuscate-emails.mjs"
```

This does not defeat a determined scraper — an entity-decoding pass costs
three lines. It defeats the bulk regex harvesters that generate most spam,
which is the actual threat.

## The surfaces it cannot reach

Entity encoding is invalid inside JSON strings, so JSON-LD stays plaintext.
Handle it by removal rather than encoding:

| Surface | Address | Protection |
|---|---|---|
| JSON-LD | none — property removed | n/a |
| HTML `mailto:` and anchor text | role address | entity-encoded at postbuild |
| Markdown mirrors, `llms-full.txt` | role address | plaintext, intentional |
| Personal address | nowhere in `dist` | — |

Three moves, in order:

1. **Drop `email` from JSON-LD.** Not a ranking signal, not a rich-result
   field, and because the graph renders on every page it was the largest
   harvestable surface — hundreds of copies of one address. Keep
   `ContactPoint` describing the channel with no address in it.
2. **Use role addresses everywhere public** — `info@`, `privacy@`. Never a
   personal address on a public surface.
3. **Name the person, route to the role.** GDPR wants a named controller;
   it does not want their personal inbox indexed:

   > Contact us at privacy@example.com. You can also email Jane Doe, owner
   > and founder, directly at the same address.

Markdown mirrors keep a plaintext role address on purpose — machine
readability is their entire function.

## Content Security Policy

**The source site had none.** Static hosting on object storage has no header
layer configured by default, so nothing was set. Fix that here.

Two options:

**CDN response headers** (preferred — `frame-ancestors` and `report-uri`
only work as real headers):

```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://plausible.io; connect-src 'self' https://plausible.io https://cms.example.com; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

**Meta tag fallback** if the CDN cannot set headers:

```astro
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; …" />
```

`'unsafe-inline'` for scripts is required by the inline `is:inline` blocks
from sprints 01 and 03. To remove it, switch those to hashes — Astro can emit
them — and drop `'unsafe-inline'`. Worth doing, not worth blocking on.

Add `frame-ancestors 'none'` unless the site is meant to be embedded.

## Privacy pages

- **Privacy policy** — controller name, contact, lawful basis per processing
  activity, retention, subject rights, and every processor named. If you use
  an ESP, it is a processor and must be listed with a DPA in place.
- **Cookie policy** — even with no cookies, saying so explicitly and
  explaining why is more reassuring than silence.
- **AI transparency** — if AI touches published content or user data, state
  where, which models, and where they run. EU AI Act Art. 50 applies to
  outputs from 2 August 2026.

## Verify

```bash
node scripts/obfuscate-emails.mjs --test
npm run build
grep -r '@example\.com' dist --include=*.html | grep -v '&#x' | head
```

The last command should return nothing outside JSON-LD-free contexts. Also
confirm every JSON-LD block still parses after the postbuild pass.

Stop. Report.
