# Sprint 09 — Booking with Calendly

**Read only this file.** ~1.5k tokens. Requires sprint 01.

## Goal

Appointment booking via Calendly, added in a way that keeps Calendly's
scripts and cookies off your pages until a visitor chooses to book. That
preserves the no-cookie-banner stance from sprint 10.

Calendly handles availability, double-booking, timezones, reminders, and
calendar invites. You give up self-hosting and hand booker data (name, email,
chosen time) to a US processor — name Calendly in your privacy policy.

## The design — link out, do not embed

```astro
<a class="button" href="https://calendly.com/YOUR-HANDLE/discovery-call"
   target="_blank" rel="noopener noreferrer">
  Book a call <span aria-hidden="true">↗</span>
</a>
```

That is the whole integration. Zero JavaScript, zero third-party requests on
your site, nothing to consent-manage, and Calendly's own page is better
tested on mobile than any embed.

The inline embed (`<div class="calendly-inline-widget">` + their widget.js)
loads ~500KB of third-party script and sets cookies **on your domain** for
every visitor who merely scrolls past it — which drags a cookie banner into a
site designed not to need one. If someone insists on-page booking is worth
that, gate it behind a click:

```astro
<!-- Static placeholder; swaps to the iframe only on click. -->
<button id="load-booking">Show booking calendar</button>
<script>
  document.getElementById('load-booking').addEventListener('click', (e) => {
    const f = document.createElement('iframe');
    f.src = 'https://calendly.com/YOUR-HANDLE/discovery-call?embed_domain='
      + location.hostname + '&embed_type=Inline';
    f.style.cssText = 'width:100%;height:700px;border:0;';
    f.title = 'Booking calendar';
    e.target.replaceWith(f);
  });
</script>
```

The click is the consent moment: nothing from Calendly loads before it.
Keep the `title` on the iframe — it is the accessible name.

## Details that matter

- **One event type per link.** Deep-link `calendly.com/handle/discovery-call`,
  not the profile page — one less choice for the visitor.
- **Prefill when you can:** `?name=…&email=…` on the URL if the visitor
  already gave them in a form. Do not put those in links you publish.
- In Calendly's settings, turn on the buffer time and minimum notice you
  actually need (e.g. 15 min buffer, 48 h notice) — defaults are zero.
- Exclude any dedicated `/appointment/` page from the sitemap; it is
  transactional, not content.
- GDPR paperwork: accept Calendly's DPA (in their admin console) and add
  Calendly to your privacy policy's processor list. Free plans include the
  DPA; you do not need a paid tier for compliance.

## Verify

- Load the booking page with the network tab open: **no** request to any
  `calendly.com` host before the click / link.
- Book a test appointment end to end; confirm the invite lands in your
  calendar and the confirmation email reaches the booker.
- Tab to the link/button and activate it with the keyboard only.

Stop. Report.
