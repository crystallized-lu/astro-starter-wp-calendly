# Sprint 08 — Contact form via WordPress

**Read only this file.** ~2.5k tokens. Requires sprint 06 (the WordPress
install it created is the form backend too).

## Goal

A contact form on the static site whose submissions are handled entirely by
WordPress: stored in the WP database, emailed to the owner, spam-filtered —
with zero custom backend code to run or maintain.

## The design

The fast static site keeps its own form (styled with sprint 01's tokens).
On submit, the browser POSTs to Contact Form 7's REST endpoint on the
WordPress install:

```
Browser ──POST──▶ WP: /wp-json/contact-form-7/v1/contact-forms/<ID>/feedback
                        │
                        ├──▶ Flamingo (stored in WP database)
                        └──▶ notification email to the owner
```

Why this over a hosted form SaaS or a hand-rolled function: the owner
already has WordPress open for blog posts, submissions live in the same
admin they already know, and there is no second vendor and no server code.
The trade: WordPress must stay up for the form to work — acceptable, since
sprint 06 already makes it a dependency for publishing.

## WordPress side — click-by-click (human does this)

1. WP admin → **Plugins → Add New**. Install and activate three:
   - **Contact Form 7** — the form engine and REST endpoint
   - **Flamingo** — same author; stores every submission in the WP database
     so nothing exists only as an email
   - **Honeypot for Contact Form 7** — invisible spam trap, no puzzle for
     humans to solve
2. **Contact → Add New**. Name it `Site contact form`. In the form template
   keep it minimal — every field you don't ask for is data you don't hold
   (GDPR data minimisation): `your-name`, `your-email`, `your-message`, plus
   an acceptance checkbox:

   ```
   [acceptance consent] I agree that my message will be stored and used to
   reply to me. See the privacy policy. [/acceptance]
   ```

3. **Mail tab**: "To" = a role address (`info@…`), never a personal inbox.
4. In the honeypot plugin's tag generator, add the honeypot field to the
   form.
5. Save, and note the **form ID** shown in the shortcode
   (`[contact-form-7 id="123" …]`) — the site needs that number.
6. Flamingo needs no setup: **Flamingo → Inbound Messages** is where
   submissions appear.

**Mail deliverability:** WP's default `wp_mail()` often lands in spam.
Install an SMTP plugin (**WP Mail SMTP** and its setup wizard) pointed at
the owner's mailbox provider or Brevo's SMTP. Send a test from the wizard
and confirm it arrives in the inbox, not spam — an unnoticed notification
is the failure mode that costs actual business.

## CORS — one snippet in WordPress

The site and WP are on different domains, so WP must say the browser may
POST across. Install **WPCode** (snippet plugin), add a PHP snippet:

```php
add_action('rest_api_init', function () {
  add_filter('rest_pre_serve_request', function ($value) {
    if (preg_match('#^/wp-json/contact-form-7/#', $_SERVER['REQUEST_URI'] ?? '')) {
      header('Access-Control-Allow-Origin: https://www.example.com');
      header('Access-Control-Allow-Methods: POST, OPTIONS');
      header('Access-Control-Allow-Headers: Content-Type');
    }
    return $value;
  });
}, 15);
```

One exact origin, only on the CF7 route. Never `*` — this endpoint writes.

## Site side

```jsx
const endpoint = `${WP_URL}/wp-json/contact-form-7/v1/contact-forms/${FORM_ID}/feedback`;

async function submit(data) {
  const body = new FormData();           // CF7 expects multipart, not JSON
  body.set('your-name', data.name);
  body.set('your-email', data.email);
  body.set('your-message', data.message);
  body.set('consent', '1');
  const res = await fetch(endpoint, { method: 'POST', body, credentials: 'omit' });
  const json = await res.json();
  // CF7 returns 200 even for failures — read status, not the HTTP code.
  return json.status === 'mail_sent'
    ? { ok: true }
    : { ok: false, message: json.message };
}
```

Two traps:

- **`FormData`, not JSON.** CF7's endpoint silently rejects JSON bodies with
  a validation error that looks like a field problem.
- **`json.status`, not `res.ok`.** CF7 answers HTTP 200 for validation
  failures and spam verdicts alike (`validation_failed`, `spam`,
  `mail_failed`). Branch on the JSON.

Client-side checks (required fields, email shape, unchecked consent box)
are UX only — CF7 re-validates server-side, which is the check that counts.

`client:visible` on the form island; it is below the fold.

## GDPR notes

- Submissions live in **two places**: Flamingo (the record) and the
  notification inbox (a copy). The privacy policy names both, plus the WP
  host and the SMTP provider as processors. Pick an EU WordPress host if EU
  data residency matters to you.
- **Retention:** decide a number (e.g. 12 months), write it in the privacy
  policy, and actually delete: Flamingo messages by hand on a calendar
  reminder, or a WP auto-delete snippet. Old enquiries are a liability, not
  an asset.
- The acceptance checkbox is **unticked by default** and required — CF7's
  `[acceptance]` tag does both. A pre-ticked box is not consent.
- Do not add analytics or tracking parameters to the form POST.

## Newsletter (optional)

Skip building one. Brevo provides a hosted signup form with double opt-in,
list storage, and unsubscribe handling built in — create it in Brevo
(**Contacts → Forms**), style it roughly to match, and link or embed it.
A newsletter backend is exactly the kind of undifferentiated machinery a
low-maintenance site should rent, and Brevo is an EU processor already in
the stack for email.

## Verify

- Submit the form from the live site: entry appears in **Flamingo →
  Inbound**, notification arrives in the inbox (not spam).
- Submit with the honeypot filled (ask the AI to POST it directly):
  no Flamingo entry, no email.
- Submit invalid data directly to the endpoint with `curl`: response JSON
  says `validation_failed` — proving validation is server-side.
- Load the form page from a different origin and confirm the browser blocks
  the POST (CORS working, one origin only).

Stop. Report.
