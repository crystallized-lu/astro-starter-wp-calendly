# Sprint 07 — Accessibility and responsive

**Read only this file.** ~4k tokens. Requires sprint 01.

## Goal

WCAG AA throughout, keyboard-complete, and a responsive system built on one
breakpoint rather than five.

## Done when

- Every interactive element is reachable and operable by keyboard alone.
- Focus is always visible.
- `prefers-reduced-motion` stops all motion.
- No horizontal scroll at 320px.

## Skip link

```astro
<a href="#main-content" class="sr-only skip-link">Skip to main content</a>
...
<main id="main-content"><slot /></main>
```

```css
.sr-only {
  position: absolute; width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

.skip-link {
  position: absolute; top: 8px; left: 8px; z-index: 9999;
  padding: 12px 24px; background: var(--purple); color: white; font-weight: 700;
}

/* On focus it must escape .sr-only's clipping — hence position + auto sizes. */
.skip-link:focus { position: fixed; width: auto; height: auto; clip: auto; }
```

## Focus

```css
a:focus-visible, button:focus-visible, input:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
  border-radius: 4px;
}
```

`:focus-visible`, not `:focus` — mouse users do not get a ring, keyboard
users always do.

Where a container clips overflow, a positive `outline-offset` is invisible.
Use an inset outline instead:

```css
.clipped-bar a:focus-visible {
  outline: 2px solid var(--light-azure);
  outline-offset: -3px;      /* negative: draws inside the clip boundary */
  border-radius: 4px;
}
```

## Never signal with colour alone

```css
/* Underline is the non-colour affordance (WCAG 1.4.1). */
.footer-link { text-decoration: underline; }
```

For nav links, a sliding underline serves hover and focus together. Use the
accent colour, not the text colour, so it reads on both light and dark nav
states:

```css
.nav-link::after {
  content: ""; position: absolute; left: 0; bottom: 0;
  width: 100%; height: 3px; background: var(--azure);
  transform: scaleX(0); transform-origin: left;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.nav-link:hover::after, .nav-link:focus-visible::after { transform: scaleX(1); }
@media (prefers-reduced-motion: reduce) { .nav-link::after { transition: none; } }
```

A colour-swap hover on an element with an inline `style="color:…"` will
silently lose to the inline style. Underlines avoid the whole problem.

## Reduced motion — global net plus local handling

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

That catches CSS. JavaScript-driven animation must check explicitly:

```js
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (reduced) {
  // Show the final state immediately. Do not animate to it faster.
  return;
}
```

## Forms

```css
.input-field[aria-invalid="true"] { border-color: #c53030; }
.input-field[aria-invalid="true"]:focus { box-shadow: 0 0 0 3px rgba(197,48,48,0.15); }
.field-error { color: #c53030; font-size: 0.8rem; }
```

Every input needs a real `<label>`. Errors are associated via
`aria-describedby`, and `aria-invalid` marks the field. Clear the error as
the user types, not on the next submit:

```jsx
const update = (field, value) => {
  setData((prev) => ({ ...prev, [field]: value }));
  if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
};
```

## Disclosure navigation, not ARIA menus

```jsx
{/* A disclosure of links, not an ARIA menu — no menu roles, because they
    promise arrow-key behaviour we do not implement. */}
```

`role="menu"` sets an expectation of full arrow-key navigation, type-ahead,
and focus wrapping. If you are not implementing that, the roles make things
worse. A `<button aria-expanded>` revealing a list of links is honest.

Escape closes and returns focus:

```jsx
useEffect(() => {
  if (!open) return;
  const onKey = (e) => {
    if (e.key === 'Escape') {
      setOpen(false);
      wrapperRef.current?.querySelector('button')?.focus();
    }
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}, [open]);
```

## Mobile drawer — full focus trap

```jsx
const wasOpenRef = useRef(false);
useEffect(() => {
  if (!menuOpen) {
    if (wasOpenRef.current) burgerRef.current?.focus();   // return focus on close
    wasOpenRef.current = false;
    return;
  }
  wasOpenRef.current = true;
  menuRef.current?.querySelector('button')?.focus();      // move focus in on open

  const onKey = (e) => {
    if (e.key === 'Escape') { setMenuOpen(false); return; }
    if (e.key !== 'Tab' || !menuRef.current) return;
    const f = menuRef.current.querySelectorAll('a[href], button:not([disabled])');
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}, [menuOpen]);
```

Markup: `role="dialog" aria-modal="true" aria-label="Navigation menu"`, plus
a body scroll lock while open.

## Tabs — the full APG pattern or none

```jsx
const handleKeyDown = (e) => {
  let next = active;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { next = (active + 1) % len; e.preventDefault(); }
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { next = (active - 1 + len) % len; e.preventDefault(); }
  else if (e.key === 'Home') { next = 0; e.preventDefault(); }
  else if (e.key === 'End') { next = len - 1; e.preventDefault(); }
  else return;
  setActive(next);
  tablistRef.current?.querySelectorAll('[role="tab"]')?.[next]?.focus();
};
```

Roving tabindex: `tabIndex={i === active ? 0 : -1}`. One tab stop for the
whole tablist, arrows move within it.

## Auto-advancing content

This is where sites reliably fail. Any carousel, cycler, or rotating panel
needs **all** of:

- A visible play/pause control (WCAG 2.2.2). Hover-pause is not enough — it
  does not exist for keyboard or touch users.
- `aria-live="off"` while rotating, `"polite"` only when paused. Announcing
  every auto-advance makes a screen reader unusable.
- Dots as real `<button>`s with `aria-label` and `aria-current`, roving
  tabindex, arrow-key support.
- Pause on `onFocus` as well as `onMouseEnter`.

```jsx
<div role="region" aria-label="Testimonials" aria-roledescription="carousel"
  onMouseEnter={pause} onMouseLeave={resume}
  onFocus={pause} onBlur={resume}>
  <div key={active} aria-live={paused ? 'polite' : 'off'} aria-atomic="true">
```

If several components share a cycler hook, put this in the **hook**, so
every consumer inherits it. The source site got it right in one carousel and
wrong in three panels driven by a shared hook — see `reference/gotchas.md`.

## Contrast

Verify tokens, not vibes. `#767676` is the lightest grey that clears 4.5:1 on
white — use it for inactive states rather than picking something lighter
because it looks calmer.

## Responsive — one breakpoint

```css
@media (max-width: 768px) {
  .hero-grid, .services-grid, .workflow-grid, .footer-grid {
    grid-template-columns: 1fr !important;
  }
  .stats-row { flex-direction: column !important; }
  .section-pad { padding-left: 24px !important; padding-right: 24px !important; }
}
```

Plus a second, narrower one only for the nav, where the burger swap happens
at a different width than the content collapse:

```css
@media (max-width: 868px) { .desktop-nav { display: none !important; } .burger-btn { display: flex !important; } }
@media (min-width: 869px) { .burger-btn { display: none !important; } }
```

The `!important` is a consequence of base styles living in inline `style=`
attributes. If you prefer to avoid it, move layout into classes from the
start — but do not mix the two approaches.

Prefer intrinsic layouts that need no query at all:

```css
grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
```

Fluid type via `clamp()`:

```css
font-size: clamp(2rem, 4.5vw, 3rem);
```

Touch targets: 44×44 minimum for the burger, close buttons, carousel
controls, and every icon-only button.

## Verify

Keyboard only — unplug the mouse. Tab through a full page: every interactive
element reachable, focus always visible, no trap except the intentional
dialog one, Escape always exits.

Then 320px width with no horizontal scroll, and one pass with a screen
reader over the nav and a form.

Report which checks you actually ran. "Should be accessible" is not a result.
