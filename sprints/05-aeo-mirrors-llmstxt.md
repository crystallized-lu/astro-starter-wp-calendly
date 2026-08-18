# Sprint 05 — Answer-engine optimization: markdown mirrors

**Read only this file.** ~4k tokens. Requires sprint 04.

## Goal

Serve a clean markdown twin of every important page, indexed by `/llms.txt`,
with a build gate that fails when a mirror drifts from its page.

## Why

An LLM fetching your HTML page pays for nav markup, inline styles, and
scripts before reaching a sentence of content. A markdown mirror is maybe a
tenth the tokens and unambiguously structured. Cheaper to read means more
likely to be read completely, and more likely to be cited accurately.

The second reason matters more: mirrors are **hand-written summaries**, not
HTML-to-markdown conversions. You control exactly what an answer engine
learns about you, in the order you want it learned.

## Done when

- `/for-ngos/index.md` returns markdown for every listed page.
- `/llms.txt` lists every mirror, grouped, and is generated not hand-written.
- `npm run build` fails if a mirror points at a route that no longer exists.

## Content collection

```ts
const mirrors = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/mirrors' }),
  schema: z.object({
    path: z.string(),                    // canonical English route
    title: z.string(),
    summary: z.string().max(160),        // the llms.txt one-liner
    structure: z.enum(['default', 'homepage', 'contact', 'about']).default('default'),
    listInMap: z.boolean().default(true),
    order: z.number().optional(),
    lastReviewed: z.coerce.date(),
    sourceHash: z.string(),              // fingerprint of the page at review time
  }),
});
```

## Mirror shape

```markdown
---
path: "/for-ngos"
title: "AI Orchestration for NGOs"
summary: "What we offer NGOs — practical, cost-conscious consulting."
structure: default
listInMap: true
order: 2
lastReviewed: 2026-04-15
sourceHash: "adaea38c78ed71f0"
---

# AI Orchestration for NGOs

## Who this is for
- Human-rights organisations operating in high-risk environments.

## Problem
…

## What we do
…

## Outcomes
…

## How we work
- See also: [Ongoing Partnership](/services/ongoing-partnership/index.md)

## Next step
Start with a no-obligation discovery call.

Canonical page: https://www.example.com/for-ngos
```

Three conventions carry the weight:

1. **Six fixed H2s, same order, every default mirror.** An answer engine
   extracting "what problem does this solve" finds it in the same slot on
   every page. Consistency across the corpus beats richness on any one page.
2. **Internal links point at other `.md` mirrors**, keeping a crawler inside
   the markdown graph instead of bouncing back into HTML.
3. **Every mirror ends with `Canonical page:`** so a citation can attribute
   to the real URL.

## The build gate — `scripts/check-mirrors.mjs`

Wire as `prebuild` so it cannot be skipped:

```json
"prebuild": "node scripts/check-mirrors.mjs",
"build": "astro build"
```

Four checks:

```js
const DEFAULT_H2S = [
  '## Who this is for', '## Problem', '## What we do',
  '## Outcomes', '## How we work', '## Next step',
];

function checkMirror(data, body) {
  const errors = [];
  if (!data) return ['Missing or malformed frontmatter'];
  if (!data.sourceHash) errors.push('Missing or empty sourceHash');
  if ((data.structure || 'default') === 'default') {
    for (const h2 of DEFAULT_H2S) {
      if (!body.includes(h2)) errors.push(`Missing canonical heading: ${h2}`);
    }
  }
  const htmlTag = body.match(/<[a-zA-Z][^>]*>/);
  if (htmlTag) errors.push(`Contains literal HTML tag: ${htmlTag[0]}`);
  return errors;
}

async function routeExists(routePath) {
  const candidates = [
    join(REPO_ROOT, 'src/pages', `${routePath}.astro`),
    join(REPO_ROOT, 'src/pages', `${routePath}/index.astro`),
  ];
  for (const c of candidates) {
    try { await access(c); return true; } catch {}
  }
  return false;
}
```

**Add the reverse check the source site lacked** — every page must also have
a mirror. One-directional validation let new pages ship with no markdown twin
and no llms.txt entry, silently:

```js
// Walk src/pages/*.astro, skip excluded routes, assert a mirror exists for each.
// Without this, the gate only catches deletions, never omissions.
```

Give the script a `--self-test` mode with fixtures asserting exact error
counts. A validator with no test is a validator you will not trust enough to
keep enforcing.

## Serving mirrors

Astro's rest parameter does not emit a route for an empty slug, so the
homepage needs its own file. This is the one non-obvious part.

`src/pages/[...mirror]/index.md.ts`:

```ts
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const mirrors = await getCollection('mirrors');
  return mirrors
    .filter((entry) => entry.data.path !== '/')
    .map((entry) => ({
      params: { mirror: entry.data.path.replace(/^\//, '') },
      props: { entry },
    }));
}

export async function GET({ props }) {
  return new Response(props.entry.body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
}
```

`src/pages/index.md.ts`:

```ts
export async function GET() {
  const mirrors = await getCollection('mirrors');
  const entry = mirrors.find((m) => m.data.path === '/');
  if (!entry) return new Response('Not found', { status: 404 });
  return new Response(entry.body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
}
```

Advertise it in `<head>`:

```astro
{mirrorPath && <link rel="alternate" type="text/markdown" href={mirrorPath} />}
```

## `/llms.txt` — derived, never hand-written

Generate from the same collection the gate validates and the routes serve.
One source, three outputs, no drift possible.

```ts
import { getCollection } from 'astro:content';

const SITE = 'https://www.example.com';
const PITCH = 'One-line description of what this organisation does.';

function groupLabel(path) {
  if (path === '/') return 'Home';
  if (path.startsWith('/for-')) return 'For audiences';
  if (path.startsWith('/services/')) return 'Services';
  if (['/about-us', '/contact'].includes(path)) return 'About';
  return 'Other';
}

export async function GET() {
  const mirrors = (await getCollection('mirrors'))
    .filter((m) => m.data.listInMap !== false)
    .sort((a, b) => (a.data.order ?? 999) - (b.data.order ?? 999)
                    || a.data.path.localeCompare(b.data.path));

  const groups = new Map();
  for (const m of mirrors) {
    const label = groupLabel(m.data.path);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(m);
  }

  const order = ['Home', 'For audiences', 'Services', 'About', 'Other'];
  const lines = ['# Example', '', `> ${PITCH}`, ''];
  for (const label of order) {
    const entries = groups.get(label);
    if (!entries?.length) continue;
    lines.push(`## ${label}`);
    for (const e of entries) {
      const url = `${SITE}${e.data.path}${e.data.path === '/' ? '' : '/'}index.md`
        .replace('//index.md', '/index.md');
      lines.push(`- [${e.data.title}](${url}): ${e.data.summary}`);
    }
    lines.push('');
  }
  lines.push('## Full brief', `- [Full brief](${SITE}/llms-full.txt)`, '');
  lines.push('## Blog', `- [RSS feed](${SITE}/blog/rss.xml)`, '');

  return new Response(lines.join('\n'), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
```

## `/llms-full.txt`

One hand-written file in `public/`. ~500 words of dense prose covering who
you serve, what you do, how you build, differentiators, and how to start.
This is the file quoted when something needs a paragraph about you — write it
to be quotable.

## Blog-post structured data for AEO

Extend the blog frontmatter schema (sprint 06) with optional AEO fields, all
Zod-validated:

- `faq` → `FAQPage` node. Directly answerable question/answer pairs.
- `mentions` → named organizations, products, or software with URLs.
- `citations` → `CreativeWork` sources with publishers.
- `howTo` → `HowTo` node with ordered steps.

Attach `author` and `publisher` by `@id` to the graph from sprint 04, so a
post stitches into the site entity rather than declaring a floating author.

## Verify

```bash
npm run build
curl -s http://localhost:4321/llms.txt | head -20
node scripts/check-mirrors.mjs --self-test
```

Then delete a page whose mirror still exists and confirm the build **fails**.
A gate you have not seen fail is not a gate.

Stop. Report.
