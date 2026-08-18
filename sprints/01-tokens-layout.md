# Sprint 01 — Design tokens and layout shell

**Read only this file.** ~3k tokens.

## Goal

One global stylesheet with contrast-checked tokens, a `BaseLayout` every page
uses, and a nav and footer that work without JavaScript.

## Done when

- Every page renders through `BaseLayout`.
- No page defines its own colour literals — all through `var(--*)`.
- Nav and footer render and are usable with JS disabled.

## Tokens — `src/styles/global.css`

Colours carry their contrast obligation in the name. The `-ink` suffix marks
a variant darkened enough for text on white; the bright version is for fills
and borders only.

```css
:root {
  --navy: #1b2b41;
  --azure: #00a8e8;          /* fills, borders, focus rings — NOT text on white */
  --azure-ink: #0072a3;      /* the text-safe azure: 4.5:1 on white */
  --light-azure: #5bb8d4;    /* links on navy backgrounds */
  --purple: #5f4b8b;
  --bg: #f9faf8;
  --white: #ffffff;
  --text: #2d3748;
  --text-muted: #4a5568;     /* still 4.5:1 on white — do not lighten */
  --border: #e2e8f0;
  --surface-muted: #f0f4f8;
  --font-display: 'Libre Baskerville', 'Libre Baskerville Fallback', Georgia, serif;
  --font-body: 'Lato', 'Lato Fallback', -apple-system, sans-serif;
  --focus-ring: 0 0 0 3px rgba(0, 168, 232, 0.4);
}
```

Rule: if a colour is used as text, it has a verified ratio and a comment
saying so. Muted grey drifts lighter every redesign unless the token blocks it.

## Layout shell — `src/layouts/BaseLayout.astro`

Props kept deliberately small. Add one only when a second page needs it.

```astro
---
interface Props {
  title: string;
  description?: string;
  ogImage?: string;
  ogType?: string;
  noindex?: boolean;
  jsonLd?: Record<string, any>;
  darkHero?: boolean;       // nav renders light-on-dark over a hero image
  rawTitle?: boolean;       // suppress the "| Site Name" suffix
  noAnalytics?: boolean;    // omit analytics entirely on sensitive pages
  lang?: string;
}

const {
  title,
  description = 'Default site description.',
  ogType = 'website',
  noindex = false,
  darkHero = false,
  rawTitle = false,
  noAnalytics = false,
  lang = 'en',
} = Astro.props;

const siteName = 'Site Name';
const fullTitle = rawTitle ? title : `${title} | ${siteName}`;
const canonicalUrl = new URL(Astro.url.pathname, Astro.site);

// Staging builds are noindexed regardless of the per-page prop. This is the
// single most valuable line in the file — it prevents a staging bucket from
// ever competing with production in search results.
const isStaging = import.meta.env.PUBLIC_SITE_ENV === 'staging';
const shouldNoindex = noindex || isStaging;
---

<!DOCTYPE html>
<html lang={lang}>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{fullTitle}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={canonicalUrl.href} />
  <link rel="sitemap" href="/sitemap-index.xml" />
  {shouldNoindex && <meta name="robots" content="noindex, nofollow" />}
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <!-- Sprint 03 adds font preloads. Sprint 04 adds OG, hreflang, JSON-LD. -->
</head>
<body>
  <a href="#main-content" class="sr-only skip-link">Skip to main content</a>

  <script is:inline>
    // Marks JS as available. Scroll-reveal hiding is scoped to html.js so
    // content is never invisible when JavaScript fails or is disabled.
    document.documentElement.classList.add('js');
  </script>

  <Navbar client:load darkHero={darkHero} lang={lang} />

  <main id="main-content">
    <slot />
  </main>

  <Footer lang={lang} />

  <script is:inline>
    // One shared IntersectionObserver for every .reveal wrapper on the page.
    // The alternative — a hydrated island per element — cost 200+ islands on
    // a long page. Reduced motion is handled in CSS, so no branch here.
    (function () {
      var els = document.querySelectorAll('.reveal:not(.is-visible)');
      if (!els.length) return;
      if (!('IntersectionObserver' in window)) {
        els.forEach(function (el) { el.classList.add('is-visible'); });
        return;
      }
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });
      els.forEach(function (el) { io.observe(el); });
    })();
  </script>
</body>
</html>
```

## Scroll reveal — `FadeIn.astro`, zero JavaScript per element

```astro
---
interface Props {
  delay?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  immediate?: boolean;   // visible in server HTML — use for above-the-fold
}
const { delay = 0, direction = 'up', immediate = false } = Astro.props;
---
<div
  class:list={['reveal', { 'is-visible': immediate }]}
  data-direction={direction}
  style={delay ? `transition-delay: ${delay}s` : undefined}
><slot /></div>
```

```css
/* Hiding is gated on html.js — no JS means no hidden content, ever. */
html.js .reveal {
  opacity: 0;
  transform: translateY(40px);
  transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1),
              transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}
html.js .reveal[data-direction='down']  { transform: translateY(-40px); }
html.js .reveal[data-direction='left']  { transform: translateX(40px); }
html.js .reveal[data-direction='right'] { transform: translateX(-40px); }
html.js .reveal[data-direction='none']  { transform: none; }
html.js .reveal.is-visible { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  html.js .reveal { opacity: 1; transform: none; transition: none; }
}
```

Three independent safety nets: no JS reveals everything, no
`IntersectionObserver` reveals everything, reduced motion reveals everything.
Never ship an animation that can leave content permanently invisible.

## Container convention

One class, one media query, applied everywhere:

```css
.section-pad { padding-left: 48px; padding-right: 48px; }
@media (max-width: 768px) {
  .section-pad { padding-left: 24px !important; padding-right: 24px !important; }
}
```

Inner width is capped per section (`max-width: 740px` for prose, 1100px for
grids). Prose caps around 740px because line length beyond ~75 characters
hurts readability more than the extra space helps.

## Verify

Build, then load a page with JavaScript disabled in devtools. All content
must be visible and the nav usable. If anything is invisible, the `html.js`
gate is wrong.

Stop here. Report. Do not open sprint 02 in this context.
