# Manual verification: the checks the repo can't answer

Some categories are only settled against the running system. Run these yourself
**only** on infrastructure the person you're working for owns and has authorised
you to test. Everything below is read-only and non-destructive; nothing here is
an exploit. When you don't have authorisation, hand the list over as a checklist
with the commands filled in.

Never run these against a third party's system.

---

## Security headers (#47)

```bash
curl -sI https://APP | tr 'A-Z' 'a-z' | grep -E \
 'strict-transport-security|content-security-policy|x-content-type-options|referrer-policy|permissions-policy|x-frame-options'
```

Want: HSTS with a long max-age; a CSP without `unsafe-inline`/`unsafe-eval`;
`nosniff`; a referrer policy; frame-ancestors set. Check the API origin too --
people configure headers on the marketing site and forget the API.

## Source maps (#37)

Load the app, note a hashed bundle filename from devtools, then:

```bash
curl -sI https://APP/_next/static/chunks/BUNDLE.js.map   # want 404
```

Also check whether the bundle ends with a `sourceMappingURL` comment.

## Debug surfaces and internal dashboards (#10, #46)

From a logged-out browser on a different network, try: `/debug`, `/__debug__`,
`/.env`, `/config`, `/metrics`, `/actuator/health`, `/graphql`, `/swagger`,
`/api-docs`, `/admin`, `/adminer.php`, `/phpmyadmin`, `/.git/config`.

```bash
for p in .env .git/config metrics actuator/health graphql swagger admin; do
  printf '%-24s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' https://APP/$p)"
done
```

Anything that isn't 401/403/404 needs an explanation. `/.git/config` returning
200 means the whole repository is downloadable.

## Staging and preview environments (#30)

List every deployment in the hosting dashboard: preview URLs, branch deploys,
`staging.`, `dev.`, `test.`, old subdomains still pointing somewhere. For each:
is it authenticated, and does it use production data or production credentials?
A preview deployment with the production `DATABASE_URL` is a complete bypass of
everything else in this report.

Check DNS records for forgotten subdomains, and whether any point at a
deprovisioned service (subdomain takeover).

## Build and deploy logs (#11)

Open the last few CI runs and the hosting provider's build logs. Search for
`sk_`, `AKIA`, `eyJ`, `-----BEGIN`, `password`, `token`. Check whether logs are
visible to people outside the team, and whether fork PRs can trigger workflows
that hold secrets.

## Database user privileges (#42)

Postgres:

```sql
\du                                  -- roles: no SUPERUSER/CREATEROLE for the app
select * from information_schema.role_table_grants where grantee = 'app_user';
select relname, relrowsecurity from pg_class
  where relnamespace = 'public'::regnamespace and relkind = 'r';  -- RLS on?
```

MongoDB: `db.getUsers()` -- the app should not be `root` or `dbOwner`.

Want: the app role can SELECT/INSERT/UPDATE/DELETE the tables it uses and
nothing more; migrations run as a different role.

## Authorization spot-checks (#5, #6, #34, #50)

With two test accounts on a system you're authorised to test:

1. Log in as A, note the id of one of A's records.
2. Log in as B, request A's record by id through the API directly.
3. Repeat for update and delete, not just read.
4. Repeat for list endpoints, search, exports, and any AI/chat endpoint that
   retrieves data.

A 200 with A's data is a confirmed IDOR. Use only accounts you created.

## Rate limits (#29)

Send a modest burst (20-30 requests) to login and to one expensive endpoint and
watch for 429s. Keep it small -- you're checking a control exists, not load
testing. Get explicit sign-off before touching a production login endpoint.

## Backups, monitoring, audit logs (#43, #44, #45)

These are questions, not commands. Ask, and record the answers verbatim:

- Where are backups, how often, what's the retention, and **when was the last
  successful restore test?** ("Never" is the usual and important answer.)
- Can the application's own credentials delete the backups?
- Who gets alerted when the error rate, auth-failure rate, or spend spikes, and
  on what channel?
- Is there a record of who did what -- logins, permission changes, exports,
  deletions -- and can an admin edit it?
- If a customer asked "what data of mine was accessed last Tuesday", could you
  answer?

## Dependencies (#38, #39)

```bash
npm audit --production        # or: pnpm audit / yarn npm audit
pip-audit                     # or: safety check
osv-scanner -r .              # language-agnostic
```

Report what's reachable from the app, not the raw count.

---

## Recording the results

For each item, write down: checked / not checked / not authorised, the evidence,
and the date. The report's credibility depends on being explicit about which
categories were verified against the live system and which were assessed from
source only.
