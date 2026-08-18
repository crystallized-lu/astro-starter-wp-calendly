# Sprint 00 — Scaffold

**Read only this file.** ~2k tokens. Do not open other sprints.

## Goal

A buildable Astro 6 static site with Preact, sitemap, markdown heading
anchors, and the config decisions that are painful to change later.

## Done when

- `npm run build` succeeds and emits `dist/`.
- `dist/sitemap-index.xml` exists.
- Visiting an old URL in the redirects table lands on the new one.

## Dependencies — keep this list short

Seven runtime deps is the target. Every addition is a maintenance cost and a
supply-chain surface.

```json
{
  "name": "site",
  "type": "module",
  "scripts": {
    "dev": "astro dev --port 4327",
    "build": "astro build",
    "preview": "astro preview"
  },
  "dependencies": {
    "@astrojs/preact": "^5.0.1",
    "@astrojs/rss": "^4.0.17",
    "@astrojs/sitemap": "^3.7.1",
    "@fontsource/lato": "^5.2.7",
    "@fontsource/libre-baskerville": "^5.2.10",
    "astro": "^6.0.0",
    "preact": "^10.29.0"
  },
  "devDependencies": {
    "rehype-autolink-headings": "^7.1.0",
    "rehype-slug": "^6.0.0",
    "vitest": "^4.1.5",
    "zod": "^4.4.3"
  }
}
```

No image-optimization dep. Astro's built-in sharp service handles it. No
compression dep — that happens at deploy (sprint 11).

## astro.config.mjs

```js
import { defineConfig } from 'astro/config';
import preact from '@astrojs/preact';
import sitemap from '@astrojs/sitemap';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';

// Pages that should never appear in the sitemap: gated flows, transactional
// pages, error pages. Anything a search result would strand a user on.
const SITEMAP_EXCLUDE = ['/404', '/500'];

export default defineConfig({
  integrations: [
    preact(),
    sitemap({
      filter: (page) => !SITEMAP_EXCLUDE.some((x) => page.includes(x)),
      lastmod: new Date(),
    }),
  ],
  output: 'static',
  site: 'https://www.example.com',
  trailingSlash: 'always',
  build: {
    // Inline the global stylesheet into each <head> so it stops being a
    // render-blocking request. Worth it while the bundle is ~10KB gzipped;
    // re-measure if it grows past ~20KB, since inlining defeats caching.
    inlineStylesheets: 'always',
  },
  markdown: {
    rehypePlugins: [
      rehypeSlug,
      [rehypeAutolinkHeadings, {
        behavior: 'append',
        properties: { className: ['heading-anchor'], ariaLabel: 'Link to this section' },
        content: { type: 'text', value: '#' },
      }],
    ],
  },
  redirects: {
    // '/old-path': '/new-path',
  },
});
```

### The four decisions worth understanding

**`site`** — the canonical origin, typed once. Everything else derives from
it. Choose www or apex now and never type the other. See
`reference/gotchas.md` on canonical drift.

**`trailingSlash: 'always'`** — pick either, but pick. Mixed trailing slashes
produce duplicate URLs, split analytics, and hreflang pairs that do not match.

**`inlineStylesheets: 'always'`** — removes one round trip before first paint.
It also means the CSS is re-sent on every page. Correct below ~20KB gzipped,
wrong above it.

**`output: 'static'`** — everything in this starter assumes static. Adding an
SSR adapter later invalidates the deploy sprint and the form architecture,
both of which route dynamic work to separate functions specifically to keep
the site static.

## Heading anchors

`rehypeSlug` + `rehypeAutolinkHeadings` give every markdown heading an `id`
and an appended `#` link. Two consequences later:

- The blog table of contents (sprint 06) reads these ids.
- Heading text gains a trailing `#`, which must be stripped when reused as
  link text. Sprint 06 does this; note it now.

## Directory layout to create

```
src/
  assets/          # images imported through astro:assets
  components/      # .astro (static) and .jsx (Preact islands)
  content/         # markdown collections
  layouts/
  pages/
  styles/
public/            # robots.txt, favicon — served verbatim, never optimized
```

Images go in `src/assets/` and are imported, not in `public/`. Only files
that must keep an exact URL belong in `public/`.

## Verify

```bash
npm install && npm run build
test -f dist/sitemap-index.xml && echo "sitemap ok"
```

Then stop. Report what was built. Do not continue to sprint 01 in this
context.
