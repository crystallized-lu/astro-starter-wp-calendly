# Stack-specific review notes

Read the section matching the stack the scanner detected (see `profile` in
`findings.json`). Each one lists where that stack's generated code tends to
break, and the fastest way to check.

---

## Next.js (App Router)

**Where secrets leak.** Any module a client component imports ships to the
browser. `NEXT_PUBLIC_*` is always public. Check that server-only modules import
`server-only` or live under `app/api/**`. Grep the built `.next/static` for key
prefixes if a build exists.

**Where auth is missing.** `middleware.ts` protects by path matcher -- read the
matcher and check what it does *not* cover. Route handlers, server actions, and
`generateMetadata` all run server-side and are individually reachable. Server
actions are the common miss: they're POST endpoints with a stable id, callable
without the UI, and they need their own auth and validation checks.

**Fast checks**
- `app/**/route.ts` files with no `auth()` / `getServerSession()` / `currentUser()`.
- `"use server"` functions that take an id and don't check the session.
- `next.config.*`: `productionBrowserSourceMaps`, a `headers()` function,
  `images.remotePatterns` set to `**`.
- Data fetched in a server component and passed to a client component -- it is
  all visible in the RSC payload, including fields you didn't render.

---

## Supabase

The anon key is public by design. **RLS is the entire security model.** If RLS is
off on any table in an exposed schema, that table is world-readable and often
world-writable through the REST API.

**Fast checks**
- Every `create table` in `supabase/migrations/**` has a matching
  `enable row level security`.
- No policy uses `using (true)` (or `with check (true)`) for anything user-owned.
- Policies compare `auth.uid()` to an owner column, and `with check` exists on
  insert/update or users can write rows they don't own.
- `service_role` key appears only in server-only code, never in a client bundle
  or an edge function that echoes it.
- Storage buckets: public vs private, and the policies on `storage.objects`.
- Database functions declared `security definer` -- they run as the owner and
  bypass RLS; check each one's internal filtering.
- Views: they don't inherit RLS the way people assume. Check `security_invoker`.

---

## Firebase

**Fast checks**
- `firestore.rules`, `storage.rules`, `database.rules.json` -- no `if true`.
- `request.auth != null` alone is authentication, not authorization. It must be
  `request.auth.uid == resource.data.ownerId` or equivalent.
- Rules on writes need `request.resource.data` validation, or a client can write
  arbitrary fields (including `role: "admin"` on their own user document).
- Storage rules should cap `request.resource.size` and check `contentType`.
- Cloud Functions: callable functions must check `context.auth` themselves;
  HTTP functions are public unless you make them otherwise.
- The Firebase web config object in client code is *not* a secret -- don't report
  it as one. The rules are what matter.

---

## Express / Fastify / Hono / Node

**Fast checks**
- Middleware order: `app.use(auth)` must come *before* the routes it protects.
  A route registered above it is unprotected.
- `cors()` with no arguments allows every origin.
- `express.json()` with no `limit` is a trivial DoS.
- Error middleware returning `err.stack`.
- `req.params` / `req.query` flowing into queries, paths, or `fetch`.
- Route files mounted but forgotten -- diff the router registrations against the
  route files that exist.
- `helmet` present *and* actually used.

---

## Django / Flask / FastAPI

**Django**: `DEBUG`, `ALLOWED_HOSTS`, `SECRET_KEY` in source, `@csrf_exempt`,
`.extra()` / `.raw()` queries, `mark_safe`, and querysets without a user filter
in views and DRF viewsets. DRF: check `permission_classes` on every viewset --
the default in `REST_FRAMEWORK` settings applies when it's missing, so read that
default first.

**Flask**: `app.run(debug=True)` (the debugger is RCE if reachable),
`render_template_string`, `send_file` with user paths, missing Flask-WTF CSRF,
`SECRET_KEY` literals.

**FastAPI**: dependencies (`Depends(get_current_user)`) present on every route
that needs them -- it's easy to add a route and forget; response models that
leak fields (`response_model` omitted on a user endpoint returns password hashes
and tokens); `CORSMiddleware` with `allow_origins=["*"]` plus
`allow_credentials=True`.

---

## Rails

`before_action :authenticate_user!` in `ApplicationController` and which
controllers `skip_before_action`; strong parameters (`params.permit`) -- a
`permit!` is mass assignment; `html_safe` / `raw` in views; `find(params[:id])`
without scoping to `current_user`; credentials in `config/master.key` (must not
be committed); `config.force_ssl`.

---

## S3 / object storage

- Public access block: all four settings on, at both account and bucket level.
- No `public-read` ACLs, no bucket policy with `"Principal": "*"`.
- Private objects served via time-limited signed URLs.
- Presigned **upload** URLs: check the server constrains key prefix, content
  type, and size -- an unconstrained presigned PUT lets a user overwrite any key.
- User-uploaded content served from a separate domain, so a stored HTML/SVG file
  can't run as your origin.
- Bucket-level encryption and versioning on; access logging somewhere the app
  can't delete.

---

## AI features (any stack)

- **Trust boundary**: list every place untrusted text reaches the model -- user
  messages, uploaded files, retrieved documents, scraped pages, tool results.
  Tool results are the one people forget: a compromised page can carry
  instructions the model then follows.
- **Tools**: for each tool the model can call, check it takes a user context and
  filters by it. A tool that runs arbitrary SQL, reads arbitrary files, or calls
  arbitrary URLs is a bypass of the app's entire authorization model.
- **Output**: model output must never be executed -- no SQL, shell, `eval`, or
  fetch built from it, and no HTML rendered from it unsanitised.
- **Spend**: per-user rate limits and a hard cap. Unmetered AI endpoints are
  routinely drained by scrapers; the first sign is the invoice.
- **Leakage**: system prompts and retrieved context are extractable. Assume
  anything you put in the prompt is public, and make sure retrieval is filtered
  by the calling user before it reaches the model, not after.
