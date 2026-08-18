# Sprint 04 — SEO and the entity graph

**Read only this file.** ~4k tokens. Requires sprint 02 if bilingual.

## Goal

Complete head metadata, and structured data that describes one entity across
the whole site rather than repeating disconnected blobs per page.

## Done when

- Every page has canonical, OG, Twitter card, and a valid JSON-LD graph.
- Every JSON-LD block parses (verify by count, not by eye).
- Breadcrumbs never link to a URL that does not exist.

## Head block

```astro
<title>{fullTitle}</title>
<meta name="description" content={description} />
<meta name="author" content={siteName} />
<link rel="canonical" href={canonicalUrl.href} />
<link rel="sitemap" href="/sitemap-index.xml" />
{shouldNoindex && <meta name="robots" content="noindex, nofollow" />}

{hreflangEntries.map((e) => <link rel="alternate" hreflang={e.hreflang} href={e.href} />)}

<meta property="og:type" content={ogType} />
<meta property="og:title" content={fullTitle} />
<meta property="og:description" content={description} />
<meta property="og:url" content={canonicalUrl.href} />
<meta property="og:image" content={socialImageUrl} />
<meta property="og:site_name" content={siteName} />
<meta property="og:locale" content={ogLocale} />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content={fullTitle} />
<meta name="twitter:description" content={description} />
<meta name="twitter:image" content={socialImageUrl} />

<link rel="alternate" type="application/rss+xml" title="Blog" href="/blog/rss.xml" />
```

Add `og:image:alt` and `og:image:width`/`height` — the source site omitted
them, and dimensions let platforms reserve space before the image loads.

## Social images by convention

Resolution order: explicit prop → generated per-page image → site-wide
default. Existence is checked at build time, so pages without one silently
fall back with no configuration.

```astro
const ogSlug = Astro.url.pathname.replace(/^\/|\/$/g, '').replace(/\//g, '-') || 'index';
const { existsSync } = await import('node:fs');
const { resolve } = await import('node:path');
const generatedOg = existsSync(resolve(`public/images/og/${ogSlug}.jpg`))
  ? new URL(`/images/og/${ogSlug}.jpg`, Astro.site).href
  : null;
const socialImageUrl = ogImage || generatedOg || new URL(defaultSocial.src, Astro.site).href;
```

So `/services/ai-orchestration/` → `services-ai-orchestration.jpg`.

**If you build a generator for these**, read `reference/gotchas.md` first.
The source site's generator hardcoded an absolute path to another repo and
was unrunnable on CI, and nothing checked that a manifest entry still matched
a real route. Declare the dependency properly and add a route-existence check.

## The entity graph

One `@graph` on every page, with `@id`-addressable nodes. Page-specific
structured data goes in a **separate** `<script>` that references those nodes
by `@id` rather than redeclaring them.

```astro
const ORG_ID = 'https://www.example.com/#organization';
const PERSON_ID = 'https://www.example.com/#founder';

const defaultJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': ORG_ID,
      name: 'Example',
      alternateName: ['Example Luxembourg'],
      legalName: 'Example SARL-S',
      url: 'https://www.example.com',
      logo: {
        '@type': 'ImageObject',
        '@id': 'https://www.example.com/#logo',
        url: 'https://www.example.com/logo.png',
        caption: 'Example',
      },
      image: { '@id': 'https://www.example.com/#logo' },   // pointer, not a copy
      description: '…',
      founder: { '@id': PERSON_ID },
      employee: { '@id': PERSON_ID },
      foundingDate: '2026',
      foundingLocation: { '@type': 'Place', name: 'Luxembourg' },
      areaServed: [
        { '@type': 'Country', name: 'Luxembourg' },
        { '@type': 'Place', name: 'European Union' },
      ],
      knowsAbout: ['Your', 'Topics', 'Here'],
      contactPoint: [{
        '@type': 'ContactPoint',
        contactType: 'customer service',
        areaServed: ['LU', 'BE', 'FR', 'DE'],
        availableLanguage: ['English', 'French'],
      }],
      sameAs: [
        'https://www.linkedin.com/company/example/',
        'https://github.com/example',
        // Include a local business directory — strong regional disambiguation.
      ],
    },
    {
      '@type': 'Person',
      '@id': PERSON_ID,
      name: 'Founder Name',
      givenName: 'Founder',
      familyName: 'Name',
      jobTitle: 'Founder',
      url: 'https://www.example.com/about-us/',
      worksFor: { '@id': ORG_ID },
      knowsLanguage: ['English', 'French'],
      sameAs: ['https://www.linkedin.com/in/founder/'],
    },
    {
      '@type': 'WebSite',
      '@id': 'https://www.example.com/#website',
      url: 'https://www.example.com',
      name: 'Example',
      publisher: { '@id': ORG_ID },
      inLanguage: lang,      // derive from the page, do not hardcode 'en'
    },
    {
      '@type': 'LocalBusiness',
      '@id': 'https://www.example.com/#localbusiness',
      name: 'Example',
      image: { '@id': 'https://www.example.com/#logo' },
      url: 'https://www.example.com',
      parentOrganization: { '@id': ORG_ID },
      address: {
        '@type': 'PostalAddress',
        streetAddress: '…', addressLocality: '…',
        postalCode: '…', addressCountry: 'LU',
      },
      geo: { '@type': 'GeoCoordinates', latitude: 0, longitude: 0 },
      priceRange: '€€',
    },
  ],
};
```

Four properties do the real work:

- **`@id` on every node** — lets other nodes point instead of duplicating.
  `logo` is declared once and referenced twice.
- **Reciprocal references** — `founder`/`worksFor` both present, both by
  `@id`. Search engines treat mutual confirmation as stronger signal.
- **`sameAs`** — the disambiguation payload. This is what links your site to
  the entity a search engine already knows about. A regional business
  directory is worth more here than another social profile.
- **`inLanguage`** — derive from the page. The source site hardcoded `'en'`
  on French pages, which is simply wrong.

Emit as separate scripts so they compose:

```astro
<script type="application/ld+json" set:html={JSON.stringify(defaultJsonLd)} />
{jsonLd && <script type="application/ld+json" set:html={JSON.stringify(jsonLd)} />}
{breadcrumbsJsonLd && <script type="application/ld+json" set:html={JSON.stringify(breadcrumbsJsonLd)} />}
```

`set:html` is safe here only because the input is `JSON.stringify` of an
object built server-side. Never pass user input through it.

## Breadcrumbs that do not 404

The trap: `/services/ai-orchestration/` naively yields Home → Services →
Page, but `/services/` may not exist. Allowlist the intermediate segments
that have real index pages:

```astro
const BREADCRUMB_PARENTS = {
  '/blog': 'Blog',
  '/services': 'Services',
};

const cleanPath = canonicalUrl.pathname.replace(/\/$/, '') || '/';
const segments = cleanPath === '/' ? [] : cleanPath.slice(1).split('/');

let breadcrumbsJsonLd = null;
if (segments.length > 0) {
  const items = [{ name: 'Home', url: 'https://www.example.com/' }];
  for (let i = 0; i < segments.length - 1; i++) {
    const prefix = '/' + segments.slice(0, i + 1).join('/');
    if (BREADCRUMB_PARENTS[prefix]) {
      items.push({ name: BREADCRUMB_PARENTS[prefix], url: 'https://www.example.com' + prefix + '/' });
    }
  }
  items.push({ name: title, url: canonicalUrl.href });
  breadcrumbsJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    '@id': canonicalUrl.href + '#breadcrumbs',
    itemListElement: items.map((it, idx) => ({
      '@type': 'ListItem', position: idx + 1, name: it.name, item: it.url,
    })),
  };
}
```

Unlisted intermediates are skipped, giving Home → current page.

## Auto-deriving service pages

If services are already listed in a `SERVICES` array for the `OfferCatalog`,
match the current path against it and emit a `Service` node automatically.
The data exists once; both uses read it.

```astro
const matchedService = SERVICES.find(
  (s) => new URL(s.url).pathname.replace(/\/$/, '') === cleanPath
);
const serviceJsonLd = matchedService ? {
  '@context': 'https://schema.org',
  '@type': 'Service',
  '@id': canonicalUrl.href + '#service',
  name: matchedService.name,
  description: matchedService.description,
  provider: { '@id': ORG_ID },
  areaServed: [{ '@type': 'Country', name: 'Luxembourg' }],
} : null;
```

## Do not put an email in JSON-LD

It is not a ranking signal and not a rich-result field, and because the graph
renders on every page it becomes your largest harvestable plaintext surface —
hundreds of copies. Entity-encoding cannot help: HTML entities are invalid
inside a JSON string.

Keep `ContactPoint` describing the *channel* (`contactType`, `areaServed`,
`availableLanguage`) with no address in it. Sprint 10 covers the rest.

## robots.txt — generate it

```
User-agent: *
Allow: /

Sitemap: https://www.example.com/sitemap-index.xml
```

Generate this from `Astro.site` rather than hand-writing it. The source site
hand-wrote it with the apex host while everything else used www.

## Verify

```bash
npm run build
# Every JSON-LD block must parse. Count blocks, count successes, compare.
grep -ro 'application/ld+json' dist --include=*.html | wc -l
```

Write a throwaway node script that extracts each block and `JSON.parse`s it.
Report "N/N parse valid", not "looks right".

Stop. Report.
