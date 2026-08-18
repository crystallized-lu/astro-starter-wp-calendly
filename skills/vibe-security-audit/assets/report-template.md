# Security audit — [PROJECT NAME]

**Prepared for:** [client / owner]
**Date:** [YYYY-MM-DD]
**Scope:** [repo name + commit SHA], [live URL if tested, or "source review only"]
**Method:** automated pattern scan + manual code review against a 50-point
checklist for AI-generated applications. [State whether the live system was
tested, and by whose authorisation.]

---

## 1. Executive summary

Three to five sentences, no jargon. What the app is, what state its security is
in, and what happens if nothing changes. Name the single worst finding in plain
language — "any logged-in customer can read every other customer's invoices" —
rather than by category.

| | Count |
|---|---|
| Critical | |
| High | |
| Medium | |
| Low | |
| Needs verification | |

*(Count these from the findings listed in section 3 — they must match, and they
must match `findings.json`.)*

**Verdict:** [Safe to launch / Launch after the critical fixes below / Not safe
to launch] — one sentence of justification.

---

## 2. Do this first (before any code changes)

Credentials that have been exposed stay exposed. Rotate these now; the code fixes
can follow.

| Credential | Where it was found | Rotate at | Done |
|---|---|---|---|
| e.g. Stripe live secret key | `.env`, committed in `a1b2c3d` | Stripe dashboard → API keys | ☐ |

Then: [take the staging environment offline / restrict the public bucket / disable
the exposed admin route] — the immediate containment steps, if any.

---

## 3. Findings

Ordered by what an attacker gets first. Repeat this block per finding.

### F-01 · [Short title] · CRITICAL · [category #N]

**Where:** `path/to/file.ts:42` (+ N similar — list them)

**What's wrong:** two or three sentences a non-specialist can follow.

**How it's exploited:** the concrete steps. If you verified it, say so and how.
If you didn't, say what would confirm it.

**Impact:** what an attacker gets — which data, how many records, what actions.

**Reachability:** confirmed reachable / entry point not found in this snapshot /
needs verification against the deployed app.

**Fix:**

```diff
- const note = await prisma.note.findUnique({ where: { id: params.id } })
+ const session = await auth()
+ if (!session?.user) return new Response("Unauthorized", { status: 401 })
+ const note = await prisma.note.findUnique({
+   where: { id: params.id, userId: session.user.id },
+ })
```

**Effort:** [10 minutes / 2 hours / 1 day] · **Fixes:** [N related findings]

---

## 4. Checked and clean

Categories reviewed with nothing to report. This is a result, and it tells the
reader what the audit actually covered.

| # | Category | Evidence |
|---|---|---|
| 17 | SQL injection | All queries use Prisma's parameterised builder; no raw SQL in the repo |

---

## 5. Not verifiable from source

Categories that need access to the running system, and what to do about each.
Pull these from the scanner's `manual_checklist` plus anything you couldn't
settle.

| # | Category | What to check | Who | Status |
|---|---|---|---|---|
| 30 | Public staging environments | Confirm preview deployments require auth and don't use production data | [owner] | ☐ |

---

## 6. Remediation plan

Sequenced by risk-reduction per hour of work, not by severity alone.

**Today** — [items], ~[N] hours
**This week** — [items], ~[N] hours
**Before scale / next release** — [items]
**Ongoing** — [dependency scanning, secret scanning in CI, audit logging, backup restore test]

---

## 7. Systemic recommendations

The habits behind the findings, not the findings themselves. Typically: a single
authorization choke point rather than per-handler checks; schema validation at
every boundary; secrets managed by the platform with rotation; RLS or equivalent
enforced in the database so an application bug can't leak everything; CI checks
(secret scan, dependency audit) so the same class of problem gets caught next
time.

---

## Appendix A — Dismissed findings

| Rule | Location | Why it's not a problem |
|---|---|---|

## Appendix B — Method and limitations

Tools and versions used, what was and wasn't in scope, and the commit audited.

State plainly: this is a source-code and configuration review, not a penetration
test. It finds patterns of insecure code; it does not prove the absence of
vulnerabilities, and it cannot find business-logic flaws that look like normal
code. [If the app handles payments, health, or regulated personal data, recommend
an independent penetration test before launch.]
