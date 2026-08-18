---
name: vibe-security-audit
description: Audit a codebase against the 50 failure modes AI-generated and "vibe-coded" apps ship with -- exposed secrets and .env files, missing auth and authorization, IDOR and cross-tenant data leaks, open Supabase/Firebase/S3 rules, SQL/NoSQL injection, XSS, CSRF, SSRF, path traversal, broken password resets, weak JWT and session handling, permissive CORS, missing rate limits, unprotected admin routes, debug pages and source maps in production, prompt injection, and missing headers, backups and monitoring. Use whenever someone asks to audit, review, pen-test, harden, or "check the security of" a repo, app, or project; asks "is this safe to launch/ship?" or "did Claude/Cursor/Lovable/v0/Bolt/Replit leave anything dangerous in here?"; or wants a client-facing security report. Use proactively before any launch, handover, or go-live review of an AI-built app, and when someone reports a suspected leak, an unexpected cloud bill, or unauthorised data access.
---

# Vibe-code security audit

AI-built apps fail security in a predictable way. The code works, so nobody looks
closer -- but the model wrote the happy path and skipped the parts nobody asked
for. Auth exists but authorization doesn't. Data is fetched by an id the caller
supplies. The `.env` got committed on the first push. Row Level Security was
never switched on. None of this shows up in normal use; all of it is a single
`curl` away for anyone who looks.

This skill runs a bundled scanner over a repository, then does the part the
scanner cannot: reading the code to decide which hits are real, finding the
holes that have no regex, and turning it into a report someone can act on.

**The scanner produces evidence, not findings.** A regex cannot tell whether an
endpoint is deliberately public or accidentally public. If you paste scanner
output into a report without opening the files, you will ship false positives to
a client and miss the worst real bug. Budget most of your effort for step 3.

## Workflow

### 1. Get the repo and set expectations

If given a path, use it. If given a GitHub URL, clone it (`git clone` -- keep
history, several checks depend on it). If the repo isn't available, ask for it
rather than guessing.

Confirm two things before starting, unless the session is unattended (then state
your assumption and continue):

- **Is this a live app with real users and real data?** That changes the severity
  of everything and makes "rotate the key" urgent rather than tidy.
- **Is there a URL you're authorised to test?** Several categories (public
  staging, exposed dashboards, live headers, served source maps) can only be
  settled against the running system. Without explicit authorisation from
  someone who owns the system, do not probe it -- put those items on the manual
  checklist instead. Never probe a third party's infrastructure.

### 2. Run the scanner

```bash
python3 <skill>/scripts/scan.py <repo-path> -o <workdir>/security-audit
```

Standard library only, read-only, no network. Add `--deep-history` to pickaxe
git history for secret shapes (slower, worth it when a leak is suspected).

It writes `findings.json` (structured: findings, repo profile, manual checklist)
and `findings.md` (the same as a triage worksheet). Read `findings.md` first --
it is ordered by severity. Use `findings.json` when you want to filter or count.

Each finding carries a **confidence**: `high` means the pattern is
near-unambiguous, `medium` means likely, `low` means "a human should look here".
Confidence is about the match, severity is about the consequence. Both matter.

Optionally, if the tools happen to be installed, their output is worth folding
in -- but never install them or hit the network without asking:
`npm audit --production`, `pip-audit`, `osv-scanner -r .`, `gitleaks detect`,
`semgrep --config auto`.

(`scripts/selftest.py` verifies the scanner still fires correctly; run it if you
ever change the rules.)

**Check the snapshot is complete before you trust it.** Does the app actually
run as committed -- are there imports with no source, referenced files that
don't exist, a single "initial commit", no lockfile? A partial snapshot changes
your conclusions: auth middleware you can't see may exist, and a route you can't
see may be the vulnerable one. Say what you were given, and ask for the rest if
it matters. This is also a finding in its own right when a client believes they
are a week from launch.

### 3. Triage -- the part that matters

Work down the findings by severity. For each one, **open the file and read
around the match**. You are answering three questions:

1. **Is it real?** Is that a live key or a placeholder? Is that route actually
   reachable? Is the interpolated value actually user-controlled?
2. **What does it cost?** Trace it to an outcome someone cares about: "any
   logged-in user can read every other customer's invoices" beats "IDOR in
   `/api/invoices/[id]`". If you can't describe the damage, you don't understand
   the finding yet.
3. **Is it the shallowest instance of a deeper pattern?** One unfiltered query
   usually means the codebase has no ownership-checking habit at all. Report the
   pattern, list the instances.

Two habits that separate a trustworthy report from a noisy one:

- **Check reachability.** A template with `|safe` that no route renders, or a
  `reset_password()` function nothing calls, is not yet a live vulnerability.
  Report it, but say the entry point is missing -- otherwise the client fixes it,
  finds it was unreachable, and discounts the rest of your report.
- **Don't assert a mitigation you haven't verified.** "The library adds a random
  suffix so URLs aren't guessable" is a claim about a version-specific default.
  Check it or write it as an assumption. Wrongly reassuring is worse than
  wrongly alarming.

`references/triage.md` has per-rule guidance on confirming or dismissing, plus
the false positives this scanner is known to produce.

Then do the passes no regex can do. Read `references/checks.md` for what "good"
looks like in each of the 50 categories, and `references/stacks.md` for the
stack you're in (Next.js, Supabase, Firebase, Express, Django/Flask, Rails, S3).
At minimum, trace these four by hand:

- **Every route, once.** List every endpoint (`app/api/**`, `pages/api/**`,
  route registrations, server actions, edge functions). For each: who can call
  it, where identity comes from, and whether the caller's right to *this
  specific record* is checked. Endpoints missing from this list are how apps get
  breached. Write the list into the report -- it is often the most valuable page.
- **One record's life.** Pick a user-owned object. Follow create → read → update
  → delete. If the owner check is missing on any one of the four, it's an IDOR.
- **The money and the privilege paths.** Anywhere a plan, credit balance, role,
  or entitlement is decided: is that decision made server-side from your own
  records, or from something the client sent?
- **The AI surface, if any.** Where does untrusted text meet the model, what
  tools can the model call, and does each tool re-check the calling user's
  permissions? An AI feature with database access and no per-user scoping is a
  data breach with a chat interface.

Also skim the git log. Generated apps often commit secrets early and remove them
later; `--deep-history` catches the common shapes, but `git log --stat` on the
first few commits is quick and revealing.

### 4. Verify what the repo can't tell you

`scan.py` emits a manual checklist for the categories that need the running
system: public staging environments, exposed dashboards, live security headers,
served source maps, build-log secrets, database user privileges, audit logs,
monitoring, backups. `references/manual-verification.md` has the exact commands.

If you're authorised and the app is live, run the safe read-only checks (header
fetch, source-map 404 check, robots/debug paths) and fold the results in. If
not, hand the checklist over with the report. Say plainly which categories you
verified and which you couldn't -- an audit that silently skips a third of its
scope is worse than one that names the gap.

### 5. Write the report

Use `assets/report-template.md`. Deliverables:

- `SECURITY-AUDIT.md` -- the report
- `findings.json` -- machine-readable findings (keep the scanner's, annotated
  with your triage verdicts: `confirmed`, `dismissed`, `needs-verification`)
- `remediation-tracker.csv` -- one row per confirmed finding with severity,
  location, fix, effort, owner, and status columns, when the client will actually
  work through the list

Send them with SendUserFile when you're done. If the report is going to a client
rather than a developer, also produce a styled HTML or PDF version -- a markdown
file is a working document, a PDF is a deliverable. Mapping findings to CWE and
OWASP Top 10 references is worth doing when the client has compliance obligations
or will forward the report to their own auditors.

Rules that keep the report useful:

- **Order by exploitability, not by category number.** What would a bored
  attacker with an account get first?
- **Every confirmed finding needs: file:line, what an attacker does, what they
  get, and a concrete fix** -- ideally a diff or the exact policy/config to
  paste. "Add authorization" is not a fix.
- **Rotate-first list at the top.** Any credential that has ever been in the
  repo or in git history is burned. That list is the first thing the owner does,
  before any code change, and it is not optional because "the repo is private" --
  private repos get forked, cloned onto laptops, and made public by accident.
- **Say what you checked and found clean.** A category with no findings is a
  result. It also stops the reader assuming you didn't look.
- **Dismissed findings go in an appendix with the reason.** It shows the work and
  stops the next auditor re-litigating them.
- **Effort estimates on the remediation plan.** "Ten minutes" vs "two days"
  determines what actually gets fixed.
- **Make the numbers agree.** The counts in the executive summary must match the
  findings you actually list, and `findings.json` must match the report. A
  summary saying "47 findings, 14 critical" above a body containing 49 findings
  and 18 criticals is the first thing a technical reader notices, and it costs
  you the benefit of the doubt on everything else. Count them at the end, from
  the list, rather than carrying an early estimate forward.

Severity = impact × exploitability, not the scanner's default. A hardcoded key
for a service that doesn't exist yet is low. A missing owner check on an
invoice endpoint in a live app is critical. Adjust and say why.

## Reference files

| File | Read it when |
|---|---|
| `references/checks.md` | Doing the reasoning pass -- what good looks like for each of the 50 categories, and how to check it |
| `references/triage.md` | Confirming or dismissing scanner hits; known false positives |
| `references/stacks.md` | The app is Next.js, Supabase, Firebase, Express, Django/Flask, Rails, or uses S3 |
| `references/manual-verification.md` | Checking the live system, or writing the handover checklist |
| `assets/report-template.md` | Writing the report |

## Scope and honesty

Static analysis finds patterns, not proofs. This skill is a strong first pass and
a good client deliverable; it is not a penetration test, and it does not replace
one for anything handling payments, health data, or regulated personal data.
Say so in the report. If you find yourself unsure whether something is exploitable,
write "needs verification" rather than picking a side -- a report that overstates
is one the client stops trusting after the first false alarm.

Never exploit a finding against a system you weren't asked to test, never test a
third party's infrastructure, and never paste a live credential into the report --
mask it and say where it lives.
