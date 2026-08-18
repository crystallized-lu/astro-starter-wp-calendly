# The 50 categories: what good looks like, and how to check

The scanner covers the mechanical half of each of these. This file is for the
reasoning pass -- what to look for once you're reading the code yourself.

Numbering follows the source checklist. Item 21 was blank in that list; it has
been filled with insecure deserialization, which sits naturally beside the other
injection categories.

**Legend** — `static`: decidable from the repo. `hybrid`: repo gives strong
evidence, confirm against the live system. `runtime`: only the live system can
answer.

---

## Secrets and configuration (1, 2, 3, 11, 13, 14)

**1. Exposed database credentials** *(static)*
Look for connection strings with inline passwords in source, config, compose
files, CI, and IaC. Good: the URL comes from an environment variable injected by
the platform, and the database is reachable only from the app's private network.
Any password that has ever been in the repo is burned -- rotation is the fix,
deleting the line is not.

**2. Public / committed .env files** *(static)*
Check three things separately: is a `.env` present, is it gitignored, and was it
*ever* committed (`git log --all --diff-filter=A --name-only | grep env`). Also
check `.env.example` for values that look real. Good: only `.env.example` with
obvious placeholders is tracked, and `.gitignore` covers `.env*` with a
`!.env.example` exception.

**3. Hardcoded API keys** *(static)*
Provider-shaped keys (`sk_live_`, `AKIA`, `AIza`, `ghp_`, `xox`) are unambiguous.
The harder case is a generic `const API_KEY = "..."`. Check what the value is
used for and whether it grants anything. Good: every credential arrives via
environment, and the repo contains no long opaque literals.

**11. Build logs leaking secrets** *(hybrid)*
Read the CI workflows: any `echo`/`env`/`printenv` step, any secret passed as a
Docker build `ARG`, any `pull_request_target` workflow that checks out fork code
while holding secrets. Then open the last few CI runs and the hosting provider's
build log and search for `sk_`, `AKIA`, `eyJ`, `BEGIN`.

**13. Leaked repos / commit history** *(hybrid)*
Even a clean HEAD can have a dirty history. Run the scanner with
`--deep-history`, or `gitleaks detect`. Also ask: is the repo public? Are there
forks? Was it ever public? Removing a secret from history does not un-leak it --
rotate, then rewrite history, in that order.

**14. Secrets in frontend JavaScript** *(static)*
Anything prefixed `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `PUBLIC_`, `EXPO_PUBLIC_`
is compiled into the browser bundle. A Supabase *anon* key there is fine and
expected; a *service_role* key is a full database compromise. Grep the built
bundle if one exists. Good: server-only secrets are read in server components,
route handlers, or server actions -- never in a module the client imports.

---

## Authentication and authorization (4, 5, 6, 9, 15, 25, 26, 27, 34, 35, 50)

**4. Weak or missing authentication** *(static)*
Where does identity come from, and is it verified on every request? Good: a
session or token validated server-side per request; passwords hashed with argon2id
or bcrypt (cost ≥ 12); a timing-safe compare for API tokens; no `DISABLE_AUTH`
escape hatch that a production env var can flip.

**5. No authorization checks** *(static)*
Authentication asks "who are you"; authorization asks "may you". Generated apps
routinely do the first and skip the second. For every handler: after identity is
resolved, is there a check that *this* user may touch *this* record? Good: a
single choke point (middleware, policy layer, `can(user, action, resource)`) that
handlers cannot forget to call.

**6. Users accessing other users' data** *(static)*
The tell is a query keyed only on an id from the request. Good: every read and
write on user-owned data carries the owner in the predicate --
`where: { id, userId: session.user.id }` -- or the database enforces it via RLS.

**9. Admin routes unprotected** *(static)*
Enumerate every admin surface: `/admin`, `/api/admin/*`, dashboards, impersonation,
data export, feature flags, seed and migration endpoints. Good: a role check in
middleware, applied by path prefix so a new admin route is protected by default.
Hiding the route from the nav is not protection.

**15. Client-side-only security checks** *(static)*
`if (user.isAdmin) return <AdminPanel/>` hides the button; it does not stop the
fetch. Good: the same rule exists in the API handler, and the client check is
purely cosmetic. Test by calling the endpoint directly.

**25. Broken password reset** *(static)*
Read the whole flow. Good: a 32-byte cryptographically random token, stored
hashed, expiring in ~15 minutes, single-use, invalidating existing sessions on
use, with the same response whether or not the account exists, and rate limited.
Bad: predictable tokens (`Math.random`, timestamps, uuidv1), no expiry, reusable,
or a "change password" endpoint that trusts an email address in the body.

**26. Weak session management** *(static)*
Good: short-lived sessions with refresh, regeneration on login and privilege
change, server-side revocation on logout and password change, tokens in HttpOnly
cookies rather than `localStorage`. Bad: non-expiring JWTs used as sessions with
no revocation path.

**27. Weak / leaked / reused JWT secrets** *(static)*
Good: a 32+ byte random secret from config, one algorithm pinned at verification,
signature and expiry always checked, different secrets per environment. Bad:
`jwt.sign(payload, "secret")`, `algorithms: ['none']`, `jwt.decode()` used where
`verify()` was meant, or the same secret in dev and prod.

**34. IDOR** *(static)*
Sequential or guessable ids plus a missing owner check. Good: ownership checked
server-side regardless of id format. UUIDs reduce discovery but are not
authorization.

**35. APIs trusting client-supplied IDs or roles** *(static)*
Anything reading `role`, `isAdmin`, `plan`, `credits`, `userId` out of the request
body. Good: those come from the session or a fresh database lookup, and the
request schema rejects them outright.

**50. Poor tenant isolation** *(static)*
In a multi-tenant app every query needs the tenant in the predicate. Good: a
scoped client or repository layer that cannot be bypassed, or RLS with a tenant
policy. Bad: `findMany({})` in a handler and a `WHERE` clause added by discipline.
Look hard at list endpoints, search, exports, and analytics -- they leak in bulk.

---

## Injection and input handling (16, 17, 18, 19, 20, 21, 22, 23, 24)

**16. Missing input validation** *(static)*
Good: every request body, query param, and path param parsed through a schema
(zod, valibot, pydantic, class-validator) at the boundary, with unknown keys
stripped. Watch for mass assignment: `prisma.user.update({ data: req.body })`
lets a caller set `role`.

**17. SQL injection** *(static)*
Template literals and f-strings inside `query`/`execute`/`raw`. Good: bound
parameters everywhere, ORM query builders, `$queryRaw` with tagged-template
parameters (never `$queryRawUnsafe`). Identifiers that must be dynamic (table,
column, sort direction) go through an allowlist, not escaping.

**18. NoSQL injection** *(static)*
`Model.find(req.body)` lets an attacker send `{"$gt": ""}` and match everything.
Good: fields picked explicitly and cast to the expected type; `$where` never used.

**19. XSS** *(static)*
`dangerouslySetInnerHTML`, `innerHTML =`, `v-html`, `|safe`, `mark_safe`,
`render_template_string`. Good: framework escaping left alone; anything that must
render HTML goes through DOMPurify/bleach with an allowlist; a CSP without
`unsafe-inline` as a second line. Stored XSS in a field that renders in an admin
view is worse than reflected -- it hits the highest-privilege user.

**20. CSRF** *(static)*
Only relevant when the browser sends credentials automatically (cookies). Good:
`SameSite=Lax` or `Strict` plus CSRF tokens or an Origin check on every
state-changing route. Bad: `SameSite=None` without tokens, `csrf_exempt` on a
POST handler, or a GET request that changes state.

**21. Insecure deserialization / unsafe eval** *(static)*
`pickle.loads`, `yaml.load` without `SafeLoader`, `unserialize`, Java
`ObjectInputStream`, and `eval`/`exec`/`new Function` on anything dynamic. Good:
JSON with a schema. This category is remote code execution when it's real.

**22. Insecure file uploads** *(static)*
Good: size cap, extension allowlist, magic-byte verification, generated
filenames, storage outside the web root (ideally a bucket that never executes),
scanning if the file is later shared, and a separate origin for user content.
Bad: `multer({dest:'uploads/'})` with no limits, or trusting `content-type`.

**23. Path traversal** *(static)*
Any filesystem path built from request input. Good: resolve the path, then verify
it still starts with the intended base directory; better, map an id to a path
server-side and never touch user strings.

**24. SSRF** *(static)*
Server-side fetches to a URL the user supplied -- webhook testers, image
importers, "fetch metadata from this link", PDF renderers. Good: an allowlist of
hosts, DNS resolution checked against private/link-local ranges, redirects
disabled, no cloud metadata access (169.254.169.254), separate egress rules.

---

## Platform, deployment and infrastructure (7, 8, 10, 12, 28, 29, 30, 31, 32, 37, 42, 46, 47, 48)

**7. Open database read/write permissions** *(static/hybrid)*
Database reachable from the internet, `trust` auth, empty passwords, a compose
file publishing 5432/27017/6379 to the host. Good: private networking, auth
required, no public port.

**8. Misconfigured Firebase / Supabase / S3** *(hybrid)*
- *Firestore/RTDB/Storage*: no `allow ... : if true`. `request.auth != null` is
  authentication, not authorization -- compare `request.auth.uid` to the document
  owner, and cap upload size and content type in Storage rules.
- *Supabase*: RLS enabled on **every** table in exposed schemas, with policies
  that reference `auth.uid()`. `using (true)` is the same as no policy. The anon
  key is public by design -- RLS is the only thing standing behind it.
- *S3*: public access block on all four settings, no `public-read` ACLs, no
  `"Principal": "*"` policies, signed URLs for private objects.

**10. Debug pages / debug mode in production** *(hybrid)*
`DEBUG = True`, `app.run(debug=True)`, `ALLOWED_HOSTS = ['*']`, GraphQL
introspection and playground, `/debug` and `/__internal` routes, verbose 500
pages. Flask's debug console is remote code execution if it's exposed. Good:
debug driven by an env var that is provably false in production, and the route
list contains nothing internal.

**12. Verbose errors leaking stack traces** *(static)*
Good: a global error handler that logs detail server-side and returns a generic
message plus a correlation id. Bad: `res.status(500).json({error: err.stack})`,
raw driver errors (they leak table and column names), or returning `str(e)`.

**28. Overly permissive CORS** *(static)*
Good: an explicit origin allowlist; credentials only for those origins. Bad:
`origin: '*'`, `cors()` with no options on a credentialed API, or reflecting the
`Origin` header (worse than `*`, because it works *with* credentials).

**29. Missing rate limits** *(static/hybrid)*
Good: per-IP and per-account limits on login, signup, password reset, OTP,
invite, and search; and per-user quotas plus a spend cap on anything that costs
money per call -- AI endpoints, email, SMS, file conversion. Bad: nothing, or
limits only in the frontend.

**30. Public test / staging environments** *(runtime)*
Enumerate every deployment: preview URLs, branch deploys, `staging.`, `dev.`,
old subdomains. Good: authentication or IP restriction on all non-production
environments, and synthetic data in them. Preview deployments with production
database credentials are a common and total bypass.

**31. Default credentials** *(static/hybrid)*
Seeded admin accounts, `admin/admin`, `POSTGRES_PASSWORD: postgres`, default
credentials on any bundled tool (Grafana, Adminer, MinIO, Redis Commander).

**32. Webhooks without signature verification** *(static)*
Good: verify the provider's signature over the **raw** body before parsing
(`stripe.webhooks.constructEvent`, Svix, HMAC compare), reject stale timestamps,
and make handlers idempotent. Bad: trusting `req.body.type` -- anyone who knows
the URL can post a fake `payment_succeeded`.

**37. Source maps in production** *(hybrid)*
`.map` files served publicly hand over your original source, including comments
and any inlined constants. Good: maps uploaded to the error tracker and excluded
from the deployed bundle. Verify with a request for the `.map` URL.

**42. Excessive database permissions** *(hybrid)*
Good: the app connects as a role with only DML on the tables it uses -- no
SUPERUSER, no CREATEDB, no ownership of migrations, and separate credentials for
migration runs.

**46. Publicly exposed internal dashboards** *(hybrid)*
Adminer, phpMyAdmin, Prisma Studio, pgAdmin, Redis Commander, Mongo Express,
Kibana, Grafana, Bull Board, Swagger UI, Traefik dashboard, `/metrics`,
`/actuator`. Good: bound to localhost, behind a VPN or SSO proxy, never on the
public app's domain.

**47. Missing security headers** *(hybrid)*
Good: HSTS with a long max-age, a CSP without `unsafe-inline`/`unsafe-eval`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy`, frame-ancestors, and a
restrictive `Permissions-Policy`. Verify against the live response, not the
config file.

**48. Cookies missing HttpOnly / Secure / SameSite** *(static)*
Good: session and auth cookies are `HttpOnly; Secure; SameSite=Lax` (or Strict),
scoped by path and domain, with a sensible max-age. Non-auth preference cookies
are a lower bar -- say so rather than reporting them at the same severity.

---

## Data handling, AI, and operations (33, 36, 38, 39, 40, 41, 43, 44, 45, 49)

**33. Frontend-only payment / subscription checks** *(static)*
Good: prices looked up server-side from your catalogue; entitlements read from
your billing records on every gated request; the fulfilment path driven by a
verified webhook, not by the browser returning from checkout. Bad: `amount` from
the request body, or `localStorage.getItem('isPro')`.

**36. Logs containing tokens, emails, passwords, PII** *(static)*
Good: structured logging with a redaction list; never log request bodies or
`Authorization` headers wholesale; scrub before events reach Sentry/PostHog.
Remember logs leave your infrastructure and are retained for months.

**38. Dependency vulnerabilities** *(hybrid)*
Run `npm audit --production`, `pip-audit`, or `osv-scanner -r .` and report what
is actually reachable -- a critical in a dev-only tool is not a critical in the
app. Good: automated scanning (Dependabot/Renovate) with someone triaging it.

**39. Outdated / unpinned packages** *(hybrid)*
Good: a committed lockfile, pinned ranges, and a regular update cadence. Bad:
`"latest"` or `*` (any upstream compromise becomes yours on the next install),
or no lockfile at all. Also flag abandoned packages and typosquat-shaped names --
generated code sometimes invents dependencies that then get registered by others.

**40. Prompt injection in AI features** *(static)*
Anywhere untrusted text reaches the model: user messages, uploaded documents,
scraped pages, emails, tool results. Good: untrusted content stays in user-role
turns with clear delimiters; the system prompt is never built by concatenation;
model output is treated as data, never executed as SQL, shell, or a URL;
irreversible tool calls need confirmation. Assume the system prompt is public.

**41. AI tools acting without permission checks** *(static)*
The dangerous shape is a model with tools that query with app-level credentials.
Good: every tool call runs through the same authorization layer as a normal
request, scoped to the calling user; tools take a user context, not free-form
SQL; destructive tools are gated. Bad: a `query_database` tool that will happily
answer "show me all users' emails".

**43. No audit logs** *(hybrid)*
Good: an append-only record of actor, action, target, timestamp, and source IP
for logins, permission changes, data exports, deletions, and admin actions --
stored where the app cannot rewrite it. Without this you cannot answer "what did
they take" after an incident.

**44. No monitoring or alerting** *(runtime)*
Good: error tracking, uptime checks, alerts on auth failure spikes, 5xx rates,
and unusual spend -- routed somewhere a human reads. Absence is not a
vulnerability but it is why breaches run for months.

**45. No backup or restore plan** *(runtime)*
Good: automated backups, point-in-time recovery, a copy the app's credentials
cannot delete, and at least one restore that has actually been performed. Backups
that have never been restored should be assumed not to work.

**49. Unencrypted sensitive data** *(static/hybrid)*
Good: TLS everywhere (no `rejectUnauthorized: false`, no `verify=False`),
encryption at rest, passwords hashed not encrypted, application-level encryption
for the genuinely sensitive columns (tokens, health, financial), and a documented
key-rotation path. Bad: plaintext or reversible storage of passwords, third-party
tokens stored raw, plain HTTP to any external service.
