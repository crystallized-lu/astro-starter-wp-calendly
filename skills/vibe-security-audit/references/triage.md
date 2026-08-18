# Triage: confirming and dismissing scanner hits

The scanner is deliberately generous. Its job is to put you in front of the
right lines; yours is to decide. This file covers how to decide quickly and what
this particular scanner gets wrong.

## The decision

For each finding, land on one of three verdicts and record it in
`findings.json`:

- **confirmed** -- you read the code and can describe the attack and its impact.
- **dismissed** -- you read the code and it is safe, with a one-line reason.
- **needs-verification** -- real if a condition holds that you can't check from
  the repo (the app is deployed, the route is reachable, the key is live). Put
  the condition in the report so someone can settle it.

Never leave a finding unjudged. An unjudged finding in a client report is worse
than no report -- it transfers your uncertainty to someone with less context.

## A fast confirmation loop

1. Open the file, read ~30 lines around the match.
2. Trace the tainted value backwards: does it originate from a request?
3. Trace the handler upwards: is there middleware, a layout guard, a decorator,
   or a framework convention that already enforces auth?
4. Grep for the sibling pattern across the repo -- one instance is usually a
   habit, and the report should say how many.
5. Decide the impact in one sentence starting "an attacker who…".

Step 3 is the one people skip, and it is where most false positives die.
Framework-level protection is invisible at the call site: Next.js `middleware.ts`,
NestJS guards, Django's `LoginRequiredMiddleware`, Rails `before_action` in a
parent controller, tRPC `protectedProcedure`, a Hono `app.use('/api/*', auth)`.
Check for it once, early, and note what it covers -- it changes the verdict on
whole classes of finding.

## Known false positives from this scanner

| Rule | Fires wrongly when | How to check |
|---|---|---|
| `SEC-GENERIC-ASSIGN` | The literal is a public key, a hash, a test vector, a CSS class, or base64 asset data | Look at what consumes it |
| `SEC-JWT-BLOB` | It's a Supabase **anon** key (public by design) or an expired test token | Decode the payload: `role: anon` is fine, `service_role` is critical |
| `AUTHZ-ROUTE-NO-AUTH` | Auth is applied by middleware, a route group layout, or a framework decorator the file never mentions | Look for `middleware.ts`, route-group layouts, guards, `before_action` |
| `TENANT-NO-SCOPE` | The app is single-tenant, or the query runs in an admin context, or RLS scopes it in the database | Check whether rows have an owner column at all |
| `IDOR-*` | The ownership filter is applied a few lines later, or the ORM has a global scope, or RLS handles it | Read the whole function, not the line |
| `CLIENT-ROLE-GATE` | The check is purely cosmetic *and* the API re-checks | Confirm the corresponding endpoint checks too -- then it's fine |
| `SSRF-FETCH` | The URL is a constant, an internal route, or from your own config | Trace the variable |
| `COOKIE-SET-NO-FLAGS` | It's a UI preference cookie (theme, sidebar), not a session | Check what's stored in it -- lower the severity, don't drop it silently |
| `EVAL-ANY` | The argument is a literal, or it's a build script, or documentation | Read the argument |
| `AUDIT-DESTRUCTIVE-NOLOG` | It's a DOM/editor teardown, not data deletion | Check the receiver |
| `AI-TOOL-NO-AUTHZ` | Tools are read-only over public data, or already user-scoped | Read each tool's implementation |
| `HEADERS-ABSENT` / `RATE-LIMIT-ABSENT` / `VALIDATION-ABSENT` | Protection comes from the platform (Vercel WAF, Cloudflare, an API gateway) or a package the profiler didn't recognise | Ask, or check the deployment config |
| `DEP-*` | The project uses a different package manager or a monorepo layout | Look for the real lockfile |
| `XSS-*` | The content is sanitised on the way in, or is a trusted constant | Find where the value is produced |
| Anything in `dist/`, `build/`, `.next/` | It's compiled output; the source is what matters | Find the source, report there |

## Where the scanner is blind

Regex cannot see these, so look for them yourself. In practice these are where
the worst finding usually is:

- **Logic flaws.** A discount code that can be applied twice. A quota checked
  before, not after, increment. A state machine that lets a refunded order ship.
- **Race conditions.** Check-then-act on balances, credits, invite seats.
- **Ownership checks in the wrong order.** Fetch, mutate, *then* check.
- **Auth that's present but wrong.** Comparing to the wrong field, checking a
  role string that no user ever has, an `||` that should be `&&`.
- **Second-order injection.** Stored input rendered later in an admin page,
  export, or email template.
- **Cross-feature leaks.** Search, exports, notifications, webhooks, and
  analytics endpoints that bypass the scoping the main read path applies.
- **Anything in a dependency or generated migration** the scanner skipped.

## Severity, recalibrated

The scanner's severity is a category default. Set your own from impact ×
exploitability:

- **Critical** -- unauthenticated or any-user access to other users' data, RCE,
  a live credential, full auth bypass, or anything that moves money.
- **High** -- requires an account or a specific condition, but yields data or
  privilege beyond the attacker's own.
- **Medium** -- needs an unlikely precondition or user interaction, or leaks
  information that helps a further attack.
- **Low** -- hardening, defence in depth, no direct path to impact.

Two adjustments worth making explicitly, because they change what gets fixed
first: multiply by *is this live with real users*, and by *how much data one
request returns*. A list endpoint missing a tenant filter is worse than a
detail endpoint missing one, because it leaks in bulk.
