# Sprint 03 — Speed: fonts, images, hydration

**Read only this file.** ~3k tokens.

## Goal

Fast first paint and near-zero layout shift, without a performance
dependency. Everything here is config and convention.

## Done when

- Lighthouse performance ≥ 95 on a production-like build.
- CLS < 0.05.
- Fewer than five hydrated islands on a typical page.

## Fonts — the fallback metrics trick

Two webfonts, imported at the top of the global stylesheet (which sprint 00
inlined into `<head>`):

```css
@import '@fontsource/lato/400.css';
@import '@fontsource/lato/700.css';
@import '@fontsource/libre-baskerville/400.css';
@import '@fontsource/libre-baskerville/700.css';
```

Then the part most sites skip. Fontsource ships `font-display: swap`, so text
paints in a system font and reflows when the webfont arrives. That reflow is
usually the single largest CLS contributor. Fix it by making the fallback
occupy identical space:

```css
@font-face {
  font-family: 'Libre Baskerville Fallback';
  src: local('Georgia');
  size-adjust: 100%;
  ascent-override: 81%;
  descent-override: 25%;
  line-gap-override: 0%;
}
@font-face {
  font-family: 'Lato Fallback';
  src: local('Arial');
  size-adjust: 97.38%;
  ascent-override: 101.34%;
  descent-override: 21.84%;
  line-gap-override: 0%;
}
```

```css
--font-display: 'Libre Baskerville', 'Libre Baskerville Fallback', Georgia, serif;
--font-body: 'Lato', 'Lato Fallback', -apple-system, sans-serif;
```

The percentages are specific to these font pairings. Changing either font
means recomputing them — use a fallback-metrics generator, do not guess.

Preload only the two 400-weight latin files, via `?url` so the hashed build
path is correct:

```astro
import latoRegularUrl from '@fontsource/lato/files/lato-latin-400-normal.woff2?url';
import baskervilleRegularUrl from '@fontsource/libre-baskerville/files/libre-baskerville-latin-400-normal.woff2?url';
```

```astro
<link rel="preload" href={baskervilleRegularUrl} as="font" type="font/woff2" crossorigin />
<link rel="preload" href={latoRegularUrl} as="font" type="font/woff2" crossorigin />
```

Display font first — headings paint before body text. Never preload bold; it
is needed later and competes for bandwidth with the LCP image.

## Images — quality tiers by role

Always `astro:assets`. Always `format="webp"`. Skip AVIF: encode time is
several times higher and the byte savings over WebP at these quality levels
do not justify it.

Quality is chosen by **how the image is used**, not by taste:

| Role | quality | widths |
|------|---------|--------|
| Blurred backdrop | 30 | `[640, 1024, 1440]` |
| Card thumbnail | 32 | `[400, 640]` |
| Full-bleed hero or band | 50 | `[640, 1024, 1440, 1920]` |
| Content-column art | 70 | `[400, 640, 900]` |
| Portrait, logo, detail | default (80) | fixed `width`/`height` |

A backdrop that gets a 30px blur applied is destroying detail anyway — paying
for quality 80 first is waste. A card thumbnail at 360px display width hides
compression artifacts that would be obvious full-bleed.

**LCP hero** — the only image on the page that gets `eager` and
`fetchpriority="high"`:

```astro
<Image
  src={heroArt} alt="" aria-hidden="true"
  loading="eager" fetchpriority="high"
  format="webp" quality={50}
  widths={[640, 1024, 1440, 1920]} sizes="100vw"
  style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center 30%;"
/>
```

At most one per page. Two `fetchpriority="high"` images means neither is
prioritized.

**Card thumbnail:**

```astro
<Image
  src={cardArt} alt="" aria-hidden="true"
  loading="lazy" format="webp" quality={32}
  widths={[400, 640]} sizes="(max-width: 768px) 100vw, 360px"
  style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;"
/>
```

Get `sizes` right or the whole exercise is pointless — a wrong `sizes` makes
the browser download the 1920px variant for a 360px slot.

**Decorative images** always get `alt="" aria-hidden="true"`. If the image
carries meaning, it needs real alt text and probably is not decorative.

**Runtime-string sources** (a CMS URL, a collection field) cannot use
`<Image>`, which needs a build-time import. Use a plain `<img>` with an
explicit `aspect-ratio` box so it still reserves space:

```astro
<div style="overflow:hidden; background:var(--bg); aspect-ratio:16/10;">
  <img src={post.data.featuredImage} alt={post.data.featuredImageAlt || ''}
       style="width:100%; height:100%; object-fit:cover; display:block;" loading="lazy" />
</div>
```

Source files in `src/assets/` can stay unoptimized — sharp handles them at
build. Do not pre-compress originals; you lose the ability to re-derive
larger variants later.

## Hydration — the ratio that matters

Target: **`client:visible` by default, `client:load` only for the first
viewport.** A healthy page is roughly 50:3 in favour of `client:visible`.

- `client:load` — navigation, and any form a user might reach in under a
  second. Nothing else.
- `client:visible` — everything else. Carousels, tabbed panels, counters,
  and yes, forms below the fold.
- Reach for `client:idle` only with a measurement showing it beats both.

Before hydrating anything, ask whether it needs to be an island. Scroll
reveals became one inline `IntersectionObserver` in sprint 01 instead of 200+
islands. Pre-paint state restoration is another case — an inline script beats
an island, because an island runs after hydration and the shift already
happened:

```astro
<script is:inline>
  // Pre-paint: collapse the dismissed banner before first paint so there is
  // no layout shift. An island would run too late to prevent it.
  try {
    if (localStorage.getItem('banner-dismissed') === '1') {
      document.documentElement.style.setProperty('--banner-h', '0px');
      document.documentElement.classList.add('banner-dismissed');
    }
  } catch (e) {}
</script>
```

## Third-party connections

Analytics loads async, but its TLS handshake otherwise starts late — worth
several hundred milliseconds of LCP:

```astro
<link rel="preconnect" href="https://plausible.io" />
<link rel="dns-prefetch" href="https://plausible.io" />
```

Only for origins actually used on that page. Speculative preconnects consume
connections and slow things down.

## Reserving space for animated numbers

A counter animating 0 → 1,247 changes width as it counts. Stack an invisible
final-value copy in the same grid cell:

```jsx
<div aria-hidden="true" style={{ fontVariantNumeric: 'tabular-nums', display: 'inline-grid', justifyItems: 'center' }}>
  <span style={{ gridArea: '1 / 1', visibility: 'hidden' }}>{value}{suffix}</span>
  <span style={{ gridArea: '1 / 1' }}>{count}{suffix}</span>
</div>
<div><span class="sr-only">{value}{suffix} — </span>{label}</div>
```

The box is sized for the final value from the first frame. The `sr-only`
span announces the result once, rather than reading every intermediate value.

## Verify

Run Lighthouse against a **production** URL, not the dev server. Dev has no
minification, no compression, and unhashed assets — its numbers are fiction.

Stop. Report the measured numbers, not "should be fast".
