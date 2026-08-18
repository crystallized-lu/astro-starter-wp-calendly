# Sprint 08 — Self-hosted form ingest

**Read only this file.** ~5k tokens. Requires sprint 00.

## Goal

Form submissions that reach your own Postgres, with no third-party form SaaS
in the data path, while the site stays fully static.

## Architecture

The site is static, so it cannot receive a POST. Rather than switching to
SSR — which would invalidate the deploy and performance sprints — dynamic
work goes to small containerized functions the browser posts to directly.

```
Browser  ──POST──▶  Scaleway Function (container)  ──▶  Postgres (private)
                            │
                            └──best-effort──▶  Brevo (email list)
```

The browser talks to the function directly. An intermediate proxy on the site
would add nothing: the function already ignores request headers and never
logs bodies, and proxying would force the whole site to SSR.

## Done when

- A submission lands in Postgres.
- The DB role used by the function can insert and nothing else.
- A bot filling the honeypot gets a 200 and writes no row.
- No request body or header is ever logged.

## Database

```sql
create extension if not exists "pgcrypto";

create table submissions (
  id uuid primary key default gen_random_uuid(),
  submitted_at timestamptz not null default now(),
  name text not null,
  email text not null,
  company text,
  message text,
  source text not null default 'contact',
  language text not null default 'en'
);

-- Read-only role for analysis. Never used by the ingest path.
create role app_reader nologin;
grant select on submissions to app_reader;

-- Ingest role: INSERT only. No select, no update, no delete.
create role app_ingest nologin;
grant insert on submissions to app_ingest;
```

The insert-only grant is the strongest control here. Even a successful SQL
injection has no read path and no destructive path. Verify it:

```sql
-- As app_ingest. Expected: permission denied.
select * from submissions limit 1;
```

Run the Postgres container with statement logging off, bound to loopback:

```bash
docker run -d --name app_db --restart unless-stopped \
  --network app_net --env-file /etc/app/db.env \
  -v /var/lib/app/db:/var/lib/postgresql/data \
  -p 127.0.0.1:5433:5432 \
  postgres:16-alpine \
  -c log_statement=none \
  -c log_min_duration_statement=-1 \
  -c log_connections=off \
  -c log_disconnections=off
```

Default statement logging writes query parameters to disk. For a form
carrying personal data, that is an unnoticed second copy with a different
retention policy.

### If anonymity is a promise, reduce timestamp precision

If you run an anonymous survey alongside a subscriber list, full-precision
timestamps let anyone with both tables re-link them by submission time.

```sql
-- Backs the "these cannot be linked" claim (GDPR Art. 5(1)(c), Art. 25).
alter table survey_responses  alter column submitted_at  set default date_trunc('minute', now());
alter table report_subscribers alter column subscribed_at set default date_trunc('hour', now());
```

Also: no foreign key, no shared id, no correlation token between the two
tables, and separate endpoints. If you promise decoupling, the schema has to
make it true.

## The function

```ts
import crypto from 'node:crypto';
import { Client } from 'pg';
import { submissionSchema } from './schema';

let invocationCounter = 0;

function jsonResponse(statusCode: number, payload: unknown) {
  return { statusCode, headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) };
}

function shortHash(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex').slice(0, 8);
}

export async function handle(event) {
  // Request headers are never read. Not filtered — never read at all, so
  // there is no code path by which an IP or user-agent could be logged.

  if ((event.httpMethod ?? 'POST').toUpperCase() !== 'POST') {
    return jsonResponse(405, { ok: false, error: 'method_not_allowed' });
  }

  let parsedBody: unknown;
  try {
    const raw = event.isBase64Encoded && event.body
      ? Buffer.from(event.body, 'base64').toString('utf8')
      : (event.body ?? '');
    parsedBody = raw ? JSON.parse(raw) : {};
  } catch {
    return jsonResponse(400, { ok: false, error: 'invalid_payload' });
  }

  const result = submissionSchema.safeParse(parsedBody);
  if (!result.success) {
    // Log a hash of the issue shape only. The raw issues can echo field
    // values back into logs, which is exactly what must not happen.
    const issueHash = shortHash(JSON.stringify(
      result.error.issues.map((i) => ({ path: i.path, code: i.code }))
    ));
    console.warn(`ingest: invalid_payload hash=${issueHash}`);
    return jsonResponse(400, { ok: false, error: 'invalid_payload' });
  }
  const data = result.data;

  const password = process.env.APP_INGEST_PW;
  if (!password) {
    console.error('ingest: APP_INGEST_PW not set');
    return jsonResponse(500, { ok: false, error: 'server_misconfigured' });
  }

  const client = new Client({
    host: process.env.APP_DB_HOST ?? 'app_db',
    port: Number(process.env.APP_DB_PORT ?? 5432),
    user: 'app_ingest',
    password,
    database: process.env.APP_DB_NAME ?? 'app',
  });

  try {
    await client.connect();
    await client.query(
      `insert into submissions (name, email, company, message, source, language)
       values ($1, $2, $3, $4, $5, $6)`,
      [data.name, data.email, data.company ?? null, data.message ?? null, data.source, data.language],
    );
  } catch (err) {
    // pg errors can include the offending query text and parameters.
    // Log a hash of the message, never the message itself.
    const message = err instanceof Error ? err.message : String(err);
    console.error(`ingest: db_error hash=${shortHash(message)}`);
    try { await client.end(); } catch {}
    return jsonResponse(500, { ok: false, error: 'insert_failed' });
  }

  try { await client.end(); } catch {}

  invocationCounter += 1;
  console.log(`ingest: ok count=${invocationCounter} at=${new Date().toISOString()}`);
  return jsonResponse(200, { ok: true });
}
```

Three logging rules, each closing a real leak: hash the validation issues,
hash the pg error, log only a counter and timestamp on success.

## Schema — every field bounded

```ts
import { z } from 'zod';

export const submissionSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email().max(320),
  company: z.string().max(150).optional(),
  message: z.string().max(3000).optional(),
  source: z.string().max(64).default('contact'),
  language: z.enum(['en', 'fr']),
  // Must be empty or absent. Any value means a bot filled a hidden field.
  honeypot: z.string().max(0).optional(),
});
```

Every string has a maximum. Every constrained value is a `z.enum`, not a
free string. An unbounded text field is a free disk-filling primitive.

**Do not duplicate this schema by hand across the site and the function.**
The source site did, with a comment asking future editors to keep both in
sync — a convention, not a mechanism. Publish it as a tiny shared package, or
add a test that imports both and asserts identical behaviour on fixtures.

## CORS — allowlist and echo

```ts
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGIN ?? 'https://www.example.com')
  .split(',').map((o) => o.trim()).filter(Boolean);

function pickAllowedOrigin(reqOrigin) {
  if (!reqOrigin) return null;
  return ALLOWED_ORIGINS.includes(reqOrigin) ? reqOrigin : null;
}
```

On a mismatch, omit the CORS header entirely rather than sending a wrong
one. Never `*` on an endpoint that writes.

Have the HTTP wrapper pass only `{ httpMethod, body }` into `handle()`, so
headers are *structurally* unable to reach the handler. That turns the
privacy promise into a type-level guarantee rather than a discipline.

## Honeypot

Hidden six ways, so it is invisible to sighted users, keyboard users, and
screen readers alike, while remaining a normal input to a naive bot:

```jsx
<div aria-hidden="true" style={{
  position: 'absolute', left: '-9999px', top: '-9999px',
  width: 0, height: 0, overflow: 'hidden', opacity: 0, pointerEvents: 'none',
}}>
  <label htmlFor="contact-website">Website</label>
  <input id="contact-website" tabIndex={-1} autoComplete="off"
         value={hp} onChange={(e) => setHp(e.target.value)} />
</div>
```

Give it a plausible name (`website`, `phone2`). On the server, return **200
with no write** — telling a bot it failed is free feedback for tuning.

## Prompt-injection filter

Only needed if submissions are ever read by an LLM — a triage agent, a
summarizer, an auto-drafted reply. If a human reads every message, skip it.

```js
const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?previous\s+(instructions|prompts)/i,
  /disregard\s+(all\s+)?(previous|prior|above)/i,
  /forget\s+(all\s+)?(previous|prior|your)\s+(instructions|rules|prompts)/i,
  /system\s*prompt/i,
  /you\s+are\s+now\s+/i,
  /new\s+instructions?\s*:/i,
  /\brole\s*:\s*(system|assistant)/i,
  /\b(BEGIN|END)\s+(SYSTEM|INSTRUCTION)/i,
  /<\/?system>/i,
  /\[\s*INST\s*\]/i,
  /<<\s*SYS\s*>>/i,
];

function detectInjection(data) {
  for (const field of ['name', 'company', 'message']) {
    if (data[field] && INJECTION_PATTERNS.some((re) => re.test(data[field]))) {
      return 'Your submission could not be processed. Please revise and try again.';
    }
  }
  return null;
}
```

This is a blunt instrument that will produce false positives on legitimate
messages about AI. It is a speed bump, not a boundary. The real control is
never putting untrusted text where it can be read as instructions.

## Client and server both validate

```jsx
const handleSubmit = async () => {
  const errs = {};
  if (!data.name.trim()) errs.name = 'Your name, please.';
  if (!validateEmail(data.email)) errs.email = 'A valid email, please.';
  if (!data.message.trim()) errs.message = 'A message, please.';
  if (!consent) errs.consent = 'Please confirm.';
  setErrors(errs);
  if (Object.keys(errs).length > 0) return;

  setSubmitting(true);
  const result = await submitForm(data, 'contact', { honeypot: hp });
  setSubmitting(false);
  result.ok ? setSubmitted(true) : setSubmitError(result.message);
};
```

Mirror `maxLength` on inputs to match the schema. And be clear about what
client checks are: **UX only.** Anyone can post directly to the endpoint.
Every cap, every pattern, every honeypot check exists server-side too.

Allowlist any query-param prefill:

```jsx
const VALID_REASONS = ['services', 'training', 'other'];
if (reason && VALID_REASONS.includes(reason)) setData((p) => ({ ...p, reason }));
```

## Third-party sync must never block

```ts
// Best-effort. Postgres is the source of truth; if the ESP is down the row
// is still saved and a CSV re-import backfills. Never throws.
async function syncToBrevo(email, language, source) {
  const key = process.env.BREVO_API_KEY;
  if (!key) return;
  const listId = Number(language === 'fr' ? process.env.BREVO_LIST_ID_FR : process.env.BREVO_LIST_ID_EN);
  if (!listId) return;
  try {
    const res = await fetch('https://api.brevo.com/v3/contacts', {
      method: 'POST',
      headers: { 'api-key': key, 'content-type': 'application/json' },
      body: JSON.stringify({ email, listIds: [listId], updateEnabled: true, attributes: { SOURCE: source } }),
      // Hard timeout — the ESP must never hold up the user's response.
      signal: AbortSignal.timeout(Number(process.env.BREVO_TIMEOUT_MS ?? 3000)),
    });
    if (!res.ok) console.warn(`brevo_sync status=${res.status}`);
  } catch (err) {
    console.warn(`brevo_sync_error hash=${shortHash(String(err))}`);
  }
}
```

## Newsletter double opt-in — stateless HMAC

Nothing is stored until confirmation, so an unconfirmed address leaves no
trace. The token is self-contained: `HMAC(email | expiry | purpose, secret)`,
7-day validity, verified by recomputation.

- Confirmation lands on **your domain**, not the API domain, and the page
  POSTs the token onward — a GET would put the token in a `Referer` header.
- `CONFIRMED_TIMESTAMP` and `CONSENT_METHOD` are set **server-side**. A
  client-supplied consent timestamp is worthless as evidence.
- Idempotent insert, so the response is identical whether or not the address
  was already subscribed:

```sql
insert into subscribers (email, language, source)
values ($1, $2, $3)
on conflict (email) do nothing
```

That prevents the endpoint from becoming an address-enumeration oracle. Same
reasoning for lookup flows: *"If that address is in our system, we have sent
a link"* — never confirm or deny.

**Behind a reverse proxy, set `trust proxy`.** Without it, every request
appears to come from the proxy's loopback address and your rate limiter keys
one shared bucket for the entire internet.

## Optimistic UI — a deliberate trade

Where the slow part is a third-party call and your own write is fast:

```tsx
// Show success immediately; let the save and ESP sync run in the background.
// The ESP round-trip is up to 3s and too slow to make the user wait.
// Trade-off: a failed request is NOT surfaced. Accepted here because
// Postgres is the sovereign record and a reconcile job can backfill.
// Add that reconcile job before relying on this at volume.
fetch(INGEST_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: trimmed, language: lang, source: 'site' }),
  credentials: 'omit',     // no cookie rides along cross-origin
}).catch(() => {});
setStatus('done');
```

Only do this when a silent failure is genuinely acceptable and a backfill
path exists. Write the reconcile job — the source site documented the need
for one and never built it.

## Cold starts

Scale-to-zero means the first submission of the day waits for a container
boot. A fire-and-forget ping when the form scrolls into view fixes it:

```ts
// no-cors GET is a simple request (no preflight). The function 405s it;
// the boot is the point.
fetch(url, { method: 'GET', mode: 'no-cors', credentials: 'omit' }).catch(() => {});
```

Only worth it if the function is genuinely cold. Measure before adding.

## Rate limiting

Platform-level: max scale 3–5 instances, 256MB each. That caps blast radius
but does not stop one abusive client. If the endpoint gets attention, add
`express-rate-limit` at the proxy — and remember `trust proxy`.

## Env vars — names only, never values

`APP_INGEST_PW`, `APP_DB_HOST`, `APP_DB_PORT`, `APP_DB_NAME`,
`BREVO_API_KEY`, `BREVO_LIST_ID_EN`, `BREVO_LIST_ID_FR`, `BREVO_TIMEOUT_MS`,
`ALLOWED_ORIGIN`, `PORT`, `NODE_ENV`.

Build-time public: `PUBLIC_INGEST_URL`, `PUBLIC_SITE_ENV`.

Anything named `PUBLIC_*` is inlined into the client bundle and is readable
by anyone. Never put a secret behind that prefix.

## Keep the API in version control

If form handling grows past these functions into a real API server, that
server belongs in a repo you can read, ideally this one. The source site's
Express API — holding the HMAC logic, rate limiter, and server-side escaping —
lived only on a VM. None of its security-critical code could be reviewed
alongside the site that depended on it.

## Verify

```bash
# Honeypot: expect 200 and zero new rows.
curl -X POST "$INGEST_URL" -H 'content-type: application/json' \
  -d '{"name":"x","email":"a@b.co","language":"en","honeypot":"filled"}'

# Oversized field: expect 400.
curl -X POST "$INGEST_URL" -H 'content-type: application/json' \
  -d "{\"name\":\"$(head -c 200 /dev/zero | tr '\0' 'a')\",\"email\":\"a@b.co\",\"language\":\"en\"}"
```

Then read the function logs and confirm no field value appears anywhere.

Stop. Report.
