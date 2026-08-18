#!/usr/bin/env python3
"""Vibe-code security scanner.

Walks a repository and reports evidence for the 50 risk categories in
catalogue.py. Pure standard library -- no installs, no network, read-only.

Usage:
    python3 scan.py <repo-path> [-o OUTDIR] [--deep-history] [--max-findings-per-rule N]

Outputs (in OUTDIR, default <repo>/../security-audit or ./security-audit):
    findings.json   machine-readable findings + repo profile + manual checklist
    findings.md     the same thing as a readable triage worksheet

The scanner deliberately errs towards reporting. Regex cannot understand a
codebase, so each finding carries a confidence level and the expectation that
a human or agent opens the file before writing it into a report.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from catalogue import CATALOGUE, SEVERITY_ORDER  # noqa: E402
from rules import compile_rules  # noqa: E402

SKIP_DIRS = {
    ".git", "node_modules", "bower_components", "vendor", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode", ".gradle", ".terraform", "target", "Pods",
    "site-packages", ".yarn", ".pnpm-store", ".turbo", ".parcel-cache",
    "coverage", ".nyc_output", ".cache", "tmp", ".DS_Store",
}
# Build output: scanned, but only for a narrow set of "did a secret ship?" rules.
BUILD_DIRS = {"dist", "build", ".next", ".nuxt", ".output", "out", "public/build", ".svelte-kit"}

BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tiff",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".mov", ".avi",
    ".webm", ".wav", ".so", ".dylib", ".dll", ".exe", ".bin", ".pyc", ".class",
    ".db", ".sqlite", ".sqlite3", ".lock", ".psd", ".ai", ".heic",
}

LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
             "Pipfile.lock", "requirements.txt", "go.sum", "Gemfile.lock", "composer.lock",
             "uv.lock", "bun.lockb"}

SECRET_FILENAMES = re.compile(
    r"(^\.env($|\.)|(^|/)\.env($|\.)|(^|/)(secrets?|credentials?|serviceaccount|service-account)"
    r"[\w.-]*\.(json|ya?ml|txt|env)$|\.pem$|\.p12$|\.pfx$|(^|/)id_(rsa|dsa|ecdsa|ed25519)$|"
    r"(^|/)\.npmrc$|(^|/)\.pypirc$|(^|/)\.netrc$|(^|/)terraform\.tfstate$)", re.IGNORECASE)

SAFE_ENV_NAMES = re.compile(r"\.env\.(example|sample|template|dist|defaults?)$|\.env\.example", re.IGNORECASE)

DOC_EXT = {".md", ".mdx", ".mdc", ".rst", ".adoc", ".txt", ".ipynb"}
# Documentation is scanned only for the categories where prose can still hurt you
# (a real key pasted into a README) -- not for code patterns it merely describes.
DOC_CATS = {1, 2, 3, 13, 14, 27, 31}

MAX_FILE_BYTES = 2_000_000
MAX_LINE_LEN = 4000


# --------------------------------------------------------------------------- utils

def sev_rank(s):
    try:
        return SEVERITY_ORDER.index(s)
    except ValueError:
        return len(SEVERITY_ORDER)


def run_git(repo, *args, timeout=45):
    try:
        r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True,
                           text=True, timeout=timeout, errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "rb") as fh:
            raw = fh.read()
        if b"\x00" in raw[:4096]:
            return None
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def redact(line):
    """Keep enough of a match to be recognisable without pasting a live key into a report."""
    line = line.strip()[:240]
    def _mask(m):
        s = m.group(0)
        return s[:4] + "*" * min(12, max(0, len(s) - 8)) + s[-4:] if len(s) > 12 else "****"
    line = re.sub(r"(?<=['\"])[A-Za-z0-9_\-\.\+/=]{20,}(?=['\"])", _mask, line)
    return line


# --------------------------------------------------------------------------- scanner

class Scanner:
    def __init__(self, repo, outdir, deep_history=False, per_rule_cap=25):
        self.repo = os.path.abspath(repo)
        self.outdir = outdir
        self.deep_history = deep_history
        self.per_rule_cap = per_rule_cap
        self.rules = compile_rules()
        self.findings = []
        self.rule_counts = Counter()
        self.suppressed = Counter()
        self.profile = {}
        self.files = []          # (relpath, abspath, ext)
        self.text_cache = {}
        self.checklist = []
        self.stats = {"files_scanned": 0, "bytes_scanned": 0, "skipped_large": 0}

    # ---- collection ------------------------------------------------------
    def collect(self):
        for root, dirs, files in os.walk(self.repo):
            rel_root = os.path.relpath(root, self.repo)
            rel_root = "" if rel_root == "." else rel_root
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != ".git"]
            for fn in files:
                rel = os.path.join(rel_root, fn) if rel_root else fn
                rel = rel.replace(os.sep, "/")
                ext = os.path.splitext(fn)[1].lower()
                if fn == "Dockerfile" or fn.startswith("Dockerfile."):
                    ext = ".Dockerfile"
                if ext in BINARY_EXT:
                    continue
                self.files.append((rel, os.path.join(root, fn), ext))

    def text(self, rel, abspath):
        if rel not in self.text_cache:
            self.text_cache[rel] = read_text(abspath)
        return self.text_cache[rel]

    # ---- reporting -------------------------------------------------------
    def add(self, cat, rule_id, title, severity, confidence, path, line_no, snippet, fix, why=None, extra=None):
        slug, cat_title, cat_sev, mode = CATALOGUE[cat]
        self.findings.append({
            "rule_id": rule_id,
            "category": cat,
            "category_slug": slug,
            "category_title": cat_title,
            "verification": mode,
            "title": title,
            "severity": severity or cat_sev,
            "confidence": confidence,
            "file": path,
            "line": line_no,
            "snippet": snippet,
            "fix": fix,
            "why": why or "",
            "detail": extra or "",
        })

    def note(self, cat, text, how):
        slug, cat_title, cat_sev, mode = CATALOGUE[cat]
        self.checklist.append({
            "category": cat, "category_title": cat_title, "severity": cat_sev,
            "item": text, "how_to_check": how,
        })

    # ---- pass 1: regex rules --------------------------------------------
    def scan_rules(self):
        for rel, abspath, ext in self.files:
            in_build = any(rel == b or rel.startswith(b + "/") for b in BUILD_DIRS) or "/dist/" in rel or "/build/" in rel
            content = self.text(rel, abspath)
            if content is None:
                self.stats["skipped_large"] += 1
                continue
            self.stats["files_scanned"] += 1
            self.stats["bytes_scanned"] += len(content)
            lines = content.split("\n")
            is_test = bool(re.search(r"(?i)(^|/)(tests?|__tests__|spec|e2e|fixtures?|mocks?|examples?)/|\.(test|spec)\.", rel))
            is_doc = ext in DOC_EXT
            fired_here = set()

            for rule in self.rules:
                if in_build and rule["cat"] not in (3, 14, 37, 1, 27):
                    continue
                if is_doc and rule["cat"] not in DOC_CATS:
                    continue
                if rule.get("ext") and ext not in rule["ext"]:
                    continue
                if rule["_pinc"] and not rule["_pinc"].search(rel):
                    continue
                if rule["_pexc"] and rule["_pexc"].search(rel):
                    continue
                if self.rule_counts[rule["id"]] >= self.per_rule_cap:
                    continue
                for i, line in enumerate(lines, 1):
                    if len(line) > MAX_LINE_LEN:
                        line = line[:MAX_LINE_LEN]
                    m = rule["_re"].search(line)
                    if not m:
                        continue
                    if rule["_not"] and rule["_not"].search(line):
                        self.suppressed[rule["id"]] += 1
                        continue
                    if rule.get("once_per_file"):
                        if rule["id"] in fired_here:
                            break
                        fired_here.add(rule["id"])
                    conf = rule["conf"]
                    sev = rule.get("sev")
                    if is_test and rule["cat"] in (3, 1, 31, 27):
                        conf = "low"
                        sev = "medium" if (sev or "high") in ("critical", "high") else sev
                    self.rule_counts[rule["id"]] += 1
                    self.add(rule["cat"], rule["id"], rule["title"], sev, conf, rel, i,
                             redact(line), rule["fix"], rule.get("why"),
                             "in build output" if in_build else ("in test/fixture code" if is_test else ""))
                    if self.rule_counts[rule["id"]] >= self.per_rule_cap:
                        break

    # ---- pass 2: repo profile -------------------------------------------
    def build_profile(self):
        names = {f[0] for f in self.files}
        joined = " ".join(names)
        pkg = {}
        for rel, abspath, ext in self.files:
            if rel.endswith("package.json") and rel.count("/") <= 2:
                try:
                    pkg.update(json.loads(self.text(rel, abspath) or "{}"))
                except Exception:
                    pass
        deps = {}
        deps.update(pkg.get("dependencies") or {})
        deps.update(pkg.get("devDependencies") or {})
        py_reqs = ""
        for cand in ("requirements.txt", "pyproject.toml", "Pipfile"):
            for rel, abspath, ext in self.files:
                if rel.endswith(cand):
                    py_reqs += (self.text(rel, abspath) or "")
        blob = (" ".join(deps.keys()) + " " + py_reqs + " " + joined).lower()

        def has(*needles):
            return any(n in blob for n in needles)

        self.profile = {
            "path": self.repo,
            "file_count": len(self.files),
            "languages": sorted({e for _, _, e in self.files if e in
                                 {".js", ".ts", ".tsx", ".jsx", ".py", ".rb", ".php", ".go", ".rs", ".java"}}),
            "frameworks": [n for n, cond in [
                ("next.js", has("next")), ("react", has("react")), ("vue", has("vue")),
                ("svelte", has("svelte")), ("express", has("express")), ("fastify", has("fastify")),
                ("nestjs", has("@nestjs")), ("django", has("django")), ("flask", has("flask")),
                ("fastapi", has("fastapi")), ("rails", has("rails")), ("laravel", has("laravel")),
                ("hono", has("hono")), ("remix", has("@remix-run")), ("astro", has("astro")),
            ] if cond],
            "data_layer": [n for n, cond in [
                ("supabase", has("supabase")), ("firebase", has("firebase")),
                ("prisma", has("prisma")), ("drizzle", has("drizzle-orm")),
                ("mongoose", has("mongoose")), ("sequelize", has("sequelize")),
                ("sqlalchemy", has("sqlalchemy")), ("knex", has("knex")),
                ("planetscale", has("planetscale")), ("neon", has("@neondatabase")),
                ("postgres", has("pg\"", "psycopg", "postgres")), ("mysql", has("mysql")),
                ("mongodb", has("mongodb")), ("redis", has("redis")),
            ] if cond],
            "auth": [n for n, cond in [
                ("next-auth", has("next-auth", "@auth/")), ("clerk", has("@clerk")),
                ("auth0", has("auth0")), ("supabase-auth", has("supabase")),
                ("firebase-auth", has("firebase")), ("lucia", has("lucia")),
                ("passport", has("passport")), ("better-auth", has("better-auth")),
                ("jsonwebtoken", has("jsonwebtoken", "jose", "pyjwt")),
                ("django-auth", has("django")), ("devise", has("devise")),
            ] if cond],
            "ai": [n for n, cond in [
                ("openai", has("openai")), ("anthropic", has("anthropic")),
                ("langchain", has("langchain")), ("vercel-ai-sdk", has("\"ai\"", " ai ")),
                ("google-genai", has("generativeai", "@google/genai")),
            ] if cond],
            "protections_present": {
                "validation_lib": has("zod", "yup", "joi", "valibot", "pydantic", "marshmallow", "class-validator", "superstruct"),
                "rate_limiter": has("rate-limit", "ratelimit", "@upstash/ratelimit", "slowapi", "django-ratelimit", "rack-attack", "bottleneck", "limiter"),
                "security_headers": has("helmet", "secure_headers", "django-csp", "flask-talisman", "next-safe"),
                "csrf": has("csurf", "csrf", "flask-wtf", "django"),
                "sanitizer": has("dompurify", "sanitize-html", "bleach", "sanitize"),
                "password_hash": has("bcrypt", "argon2", "scrypt", "passlib", "werkzeug"),
                "orm": has("prisma", "drizzle", "sequelize", "sqlalchemy", "mongoose", "typeorm", "activerecord"),
                "error_tracking": has("sentry", "bugsnag", "rollbar", "datadog", "honeybadger", "opentelemetry"),
                "secret_scanning": has("gitleaks", "trufflehog", "detect-secrets", "talisman"),
                "dependency_scanning": has("dependabot", "renovate", "snyk", "npm audit", "safety"),
                "tests": bool(re.search(r"(?i)(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?", joined)),
            },
            "lockfiles": sorted({os.path.basename(n) for n in names if os.path.basename(n) in LOCKFILES}),
            "ci": sorted({n for n in names if re.search(r"(?i)(\.github/workflows/|\.gitlab-ci|Jenkinsfile|azure-pipelines|\.circleci/)", n)})[:20],
            "is_git_repo": os.path.isdir(os.path.join(self.repo, ".git")),
        }
        self.profile["dependencies"] = deps

    # ---- pass 3: structural checks --------------------------------------
    def scan_structure(self):
        names = {f[0] for f in self.files}
        gitignore = ""
        for cand in (".gitignore", ".dockerignore"):
            p = os.path.join(self.repo, cand)
            if os.path.exists(p):
                gitignore += read_text(p) or ""
        ignores_env = bool(re.search(r"^\s*\*?\.?env", gitignore, re.MULTILINE))

        tracked = set()
        if self.profile.get("is_git_repo"):
            tracked = {l.strip() for l in run_git(self.repo, "ls-files").splitlines() if l.strip()}

        # --- 2: env and secret files -------------------------------------
        for rel, abspath, ext in self.files:
            base = os.path.basename(rel)
            if not SECRET_FILENAMES.search(rel) and not SECRET_FILENAMES.search(base):
                continue
            is_sample = bool(SAFE_ENV_NAMES.search(base))
            content = self.text(rel, abspath) or ""
            looks_real = bool(re.search(
                r"=\s*['\"]?[A-Za-z0-9_\-/+=\.]{16,}['\"]?\s*$", content, re.MULTILINE)) and not re.search(
                r"(?i)(your[-_ ]|example|changeme|xxxx|<.*>|placeholder)", content)
            in_git = rel in tracked
            if in_git and not is_sample:
                self.add(2, "ENV-TRACKED", "Secret file is committed to git", "critical", "high",
                         rel, 1, base, "Remove from the index (git rm --cached), rotate everything in it, and add it to .gitignore.",
                         "Anything in git is in every clone, every fork, and every CI runner that checks out the repo.")
            elif is_sample and looks_real:
                self.add(2, "ENV-SAMPLE-REAL", "Example env file appears to contain real values", "high", "medium",
                         rel, 1, base, "Replace the values with obvious placeholders.")
            elif not is_sample:
                self.add(2, "ENV-PRESENT", "Secret file present in the working tree", "medium",
                         "high" if not ignores_env else "low", rel, 1, base,
                         "Confirm it is gitignored and never copied into a container image or deploy bundle." +
                         ("" if ignores_env else " .gitignore does not appear to cover env files."))

        if not ignores_env and self.profile.get("is_git_repo"):
            self.add(2, "GITIGNORE-NO-ENV", ".gitignore does not exclude env files", "high", "high",
                     ".gitignore", 1, "(no .env entry found)",
                     "Add `.env`, `.env.*`, `!*.example` to .gitignore before someone commits a live key.")

        # --- 13: git history ---------------------------------------------
        if self.profile.get("is_git_repo"):
            hist = run_git(self.repo, "log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A")
            ever = {l.strip() for l in hist.splitlines() if l.strip()}
            leaked = sorted(p for p in ever if SECRET_FILENAMES.search(p) and not SAFE_ENV_NAMES.search(os.path.basename(p)))
            for p in leaked[:20]:
                self.add(13, "GIT-HIST-SECRET-FILE", "Secret file exists in commit history", "critical", "high",
                         p, 1, p,
                         "Rotate every credential it ever held. Removing the file from HEAD does not remove it from history; "
                         "use git-filter-repo or BFG and force-push, then assume the old values are public.")
            remotes = run_git(self.repo, "remote", "-v")
            if remotes.strip():
                self.profile["remotes"] = sorted({l.split()[1] for l in remotes.splitlines() if len(l.split()) > 1})
            if self.deep_history:
                self.scan_history_content()
            else:
                self.note(13, "Check whether the repository (or a fork/gist) is public and whether history contains secrets.",
                          "Run this scanner with --deep-history, or run `gitleaks detect --no-git=false`. "
                          "Also check GitHub for forks and for the repo's visibility setting.")

        # --- 37: shipped source maps -------------------------------------
        maps = [rel for rel, _, _ in self.files if rel.endswith(".map")]
        maps += [rel for rel, _, _ in [(f[0], f[1], f[2]) for f in self.files]
                 if re.search(r"\.(js|css)\.map$", rel)]
        for rel in sorted(set(maps))[:15]:
            self.add(37, "SOURCEMAP-FILE", "Source map committed or present in build output", "medium", "high",
                     rel, 1, os.path.basename(rel),
                     "Exclude .map files from the deployed bundle, or upload them to your error tracker and delete them from the public directory.")

        # --- 38/39: dependency hygiene -----------------------------------
        deps = self.profile.get("dependencies") or {}
        loose = [f"{k}@{v}" for k, v in deps.items() if isinstance(v, str) and v.strip() in ("*", "latest", "")]
        if loose:
            self.add(39, "DEP-UNPINNED", "Dependencies pinned to '*' or 'latest'", "medium", "high",
                     "package.json", 1, ", ".join(loose[:8]),
                     "Pin to a range you control. 'latest' makes builds non-reproducible and turns any upstream compromise into your compromise.")
        if deps and not self.profile["lockfiles"]:
            self.add(39, "DEP-NO-LOCKFILE", "No lockfile committed", "medium", "high",
                     "package.json", 1, "(no package-lock.json / yarn.lock / pnpm-lock.yaml)",
                     "Commit the lockfile so deploys install the exact versions you tested.")
        for rel, abspath, ext in self.files:
            if os.path.basename(rel) == "requirements.txt":
                body = self.text(rel, abspath) or ""
                unpinned = [l.strip() for l in body.splitlines()
                            if l.strip() and not l.strip().startswith("#") and not re.search(r"[=<>~!]", l)]
                if unpinned:
                    self.add(39, "DEP-PY-UNPINNED", "Unpinned Python dependencies", "medium", "high",
                             rel, 1, ", ".join(unpinned[:8]),
                             "Pin with == and refresh deliberately, or use a lockfile (uv/poetry/pip-tools).")
        if not self.profile["protections_present"]["dependency_scanning"]:
            self.note(38, "No automated dependency scanning is configured.",
                      "Run `npm audit --production` / `pip-audit` / `osv-scanner -r .` now, and enable Dependabot or Renovate for the future.")
        else:
            self.note(38, "Dependency scanning tooling is referenced -- confirm it actually runs and that alerts are acted on.",
                      "Check the CI config and the repository's security tab for open alerts.")

        # --- absence checks: 29, 47, 16, 43, 44, 45 ----------------------
        prot = self.profile["protections_present"]
        self.scan_route_files()
        has_auth_routes = any(
            re.search(r"(?i)(login|signin|sign-in|signup|register|password|/auth)", rel) or
            re.search(r"(?i)(login|signin|signup|register|reset[-_ ]?password|createUser|signInWith)",
                      (self.text(rel, abspath) or "")[:200000])
            for rel, abspath, ext in self.files if ext in {".js", ".ts", ".tsx", ".jsx", ".py", ".rb", ".go", ".php"})
        if has_auth_routes and not prot["rate_limiter"]:
            self.add(29, "RATE-LIMIT-ABSENT", "No rate-limiting library found anywhere in the project", "high", "medium",
                     "(project-wide)", 0, "no rate-limit dependency detected",
                     "Add per-IP and per-account limits to login, signup, password reset, OTP, and any paid/AI endpoint. "
                     "Credential stuffing against an unlimited login endpoint is fully automated these days.")
        header_evidence = any(
            re.search(r"(?i)(strict-transport-security|content-security-policy|x-content-type-options|"
                      r"referrer-policy|async\s+headers\s*\(|helmet\(|SecurityMiddleware|Talisman\()",
                      self.text(rel, abspath) or "")
            for rel, abspath, ext in self.files
            if ext in {".js", ".ts", ".mjs", ".py", ".rb", ".toml", ".json", ".yml", ".yaml", ".conf"} and rel.count("/") <= 3)
        if header_evidence:
            prot["security_headers"] = True
        if self.profile["frameworks"] and not prot["security_headers"]:
            self.add(47, "HEADERS-ABSENT", "No security-header middleware configured", "medium", "medium",
                     "(project-wide)", 0, "no helmet / CSP / HSTS configuration detected",
                     "Add helmet (Express), `headers()` in next.config, Talisman (Flask), or SecurityMiddleware (Django): "
                     "CSP, HSTS, X-Content-Type-Options, Referrer-Policy, X-Frame-Options.")
        if not prot["validation_lib"]:
            self.add(16, "VALIDATION-ABSENT", "No schema validation library in the dependency list", "high", "medium",
                     "(project-wide)", 0, "no zod / yup / joi / pydantic / class-validator detected",
                     "Validate and narrow every request body, query param, and header at the boundary. "
                     "Most injection and mass-assignment bugs die here.")
        if not prot["password_hash"] and any("password" in (self.text(r, a) or "").lower()
                                             for r, a, e in self.files[:400] if e in (".js", ".ts", ".py")):
            self.add(49, "HASH-ABSENT", "No password hashing library detected while password handling is present",
                     "critical", "low", "(project-wide)", 0, "no bcrypt / argon2 / passlib detected",
                     "If you store passwords, hash them with argon2id or bcrypt. If auth is delegated to a provider, note that in the report and dismiss this.")
        if not prot["error_tracking"]:
            self.note(44, "No error tracking or monitoring integration found.",
                      "Add Sentry (or equivalent) plus uptime checks and an alert route that a human actually reads.")
        self.note(43, "Confirm whether privileged and destructive actions are recorded in an append-only audit log.",
                  "Look for an audit/activity table, or logs that capture actor + action + target + timestamp for role changes, deletions, and data exports.")
        self.note(45, "Confirm backups exist and that a restore has actually been tested.",
                  "Check the database provider's PITR/backup settings and run one real restore into a scratch database.")
        self.note(30, "Confirm no staging, preview, or test deployment is publicly reachable with production data.",
                  "List every deployment (Vercel previews, Netlify branch deploys, Render/Fly staging). Password-protect them and give them their own throwaway data.")
        self.note(46, "Confirm internal dashboards and DB tools are not internet-reachable.",
                  "Try loading /admin, /metrics, /actuator, adminer, and any studio/dashboard URL from a logged-out browser on a different network.")
        self.note(42, "Confirm the database user the app connects as has only the privileges it needs.",
                  "In Postgres: `\\du` and check for SUPERUSER/CREATEDB; the app should not own migrations or be able to DROP.")
        self.note(11, "Confirm build and deploy logs do not contain secrets.",
                  "Open the last few CI runs and the hosting provider's build logs and search for key prefixes (sk_, AKIA, eyJ, -----BEGIN).")
        self.note(47, "Verify the deployed response headers, not just the code.",
                  "curl -sI https://<your-domain> and check for strict-transport-security, content-security-policy, x-content-type-options, referrer-policy.")
        self.note(37, "Verify no source maps are served in production.",
                  "curl -sI https://<domain>/<hashed-bundle>.js.map and confirm a 404.")

        # --- 8: BaaS config files present but unreviewed ------------------
        for marker, cat, msg in [
            ("firestore.rules", 8, "Firestore rules file found -- read it line by line; the default template is permissive."),
            ("storage.rules", 8, "Firebase Storage rules found -- confirm uploads are owner-scoped and size-limited."),
            ("database.rules.json", 8, "Realtime Database rules found -- confirm no `true` grants."),
        ]:
            if any(rel.endswith(marker) for rel, _, _ in self.files):
                self.note(cat, msg, "Open the file and check every allow/rule against 'which user should be able to do this'.")

        if "supabase" in self.profile["data_layer"]:
            sql_files = [(r, a) for r, a, e in self.files if e == ".sql" or "/migrations/" in r]
            enabled = set()
            created = set()
            for r, a in sql_files:
                body = self.text(r, a) or ""
                for m in re.finditer(r"(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?[\"']?(?:public\.)?[\"']?(\w+)", body):
                    created.add(m.group(1).lower())
                for m in re.finditer(r"(?i)alter\s+table\s+[\"']?(?:public\.)?[\"']?(\w+)[\"']?\s+enable\s+row\s+level\s+security", body):
                    enabled.add(m.group(1).lower())
            missing = sorted(created - enabled)
            if missing:
                self.add(8, "SB-RLS-MISSING", "Supabase tables created without enabling Row Level Security",
                         "critical", "high", "(migrations)", 0, ", ".join(missing[:12]),
                         "Run `alter table X enable row level security;` and add policies. Without RLS the public anon key can read and write the whole table from a browser.")
            elif created:
                self.note(8, "RLS statements found for the tables in migrations -- confirm the policies themselves are owner-scoped.",
                          "In the Supabase dashboard, check each policy's USING/WITH CHECK expression references auth.uid().")

    def scan_route_files(self):
        """File-level checks that a line-by-line regex cannot make.

        The question these answer is "does this file that clearly handles
        requests ever mention authentication or authorization at all?" A route
        file with zero auth vocabulary is the signature failure of a generated
        app: the endpoint works, and it works for everybody.
        """
        AUTH_WORDS = re.compile(
            r"(?i)(getServerSession|auth\(\)|getUser\(|currentUser|requireAuth|isAuthenticated|"
            r"verifyToken|jwt\.verify|jwtVerify|@login_required|login_required|IsAuthenticated|"
            r"authenticate|authorize|permission|ensureLogged|withAuth|clerkClient|getAuth|"
            r"session\.user|req\.user|request\.user|current_user|before_action|middleware\.auth|"
            r"supabase\.auth|checkAuth|guard|can\(|abilities|policy)")
        ROUTE_SIGNS = re.compile(
            r"(?i)(\w+\.(get|post|put|patch|delete|all)\s*\(\s*['\"`]/|export\s+(async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)|"
            r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\s*=|@\w+\.(route|get|post|put|patch|delete)\s*\(|"
            r"@(Get|Post|Put|Patch|Delete)\(|@api_view|http\.HandleFunc|router\.(get|post|put|delete))")
        WRITES = re.compile(
            r"(?i)\.(create|createMany|update|updateMany|upsert|delete|deleteMany|insert|save|remove|destroy)\s*\(|"
            r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b")
        CSRF_WORDS = re.compile(r"(?i)(csrf|xsrf|double[-_ ]?submit|origin\s*check|sameSite\s*[:=]\s*['\"]?(lax|strict))")
        cookie_auth = False
        csrf_present = False

        for rel, abspath, ext in self.files:
            if ext not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".py", ".rb", ".go", ".php"}:
                continue
            if re.search(r"(?i)(^|/)(tests?|__tests__|spec|e2e)/|\.(test|spec)\.", rel):
                continue
            body = self.text(rel, abspath) or ""
            if not body:
                continue
            if re.search(r"(?i)(res\.cookie|set_cookie|setCookie|cookies\(\)\.set|session\[)", body):
                cookie_auth = True
            if CSRF_WORDS.search(body):
                csrf_present = True
            if not ROUTE_SIGNS.search(body):
                continue
            if AUTH_WORDS.search(body):
                continue
            # A public-by-design route file (health checks, marketing pages, auth itself) is fine;
            # a route file that reads or writes data without any auth vocabulary is not.
            is_authish = re.search(r"(?i)(login|signup|register|signin|auth|health|status|public|webhook|stripe)", rel)
            touches_data = bool(WRITES.search(body)) or bool(
                re.search(r"(?i)\.(find|findMany|findOne|findUnique|select|query|aggregate)\s*\(", body))
            if touches_data and not is_authish:
                sev = "critical" if WRITES.search(body) else "high"
                self.add(5, "AUTHZ-ROUTE-NO-AUTH",
                         "Request handler touches data with no authentication or authorization reference",
                         sev, "medium", rel, 1,
                         "no session/auth/permission check found anywhere in this file",
                         "Resolve the caller's identity at the top of the handler and check they are allowed to touch this "
                         "specific record. If this endpoint is deliberately public, say so in a comment so the next reader knows.")

        if cookie_auth and not csrf_present:
            self.add(20, "CSRF-ABSENT", "Cookie-based sessions with no CSRF defence found", "high", "medium",
                     "(project-wide)", 0, "cookies are set but no CSRF token, SameSite, or origin check was found",
                     "Set SameSite=Lax or Strict on session cookies and add CSRF tokens (or an Origin check) to every "
                     "state-changing route. Without this any site the user visits can act as them.")

        self.scan_ai_files()
        if self.profile.get("ai"):
            self.note(41, "AI features detected -- confirm every tool/function the model can call re-checks the calling user's permissions.",
                      "For each tool the model can invoke, trace whether it filters by the caller's user/tenant id, or whether it queries with app-level credentials.")
            self.note(40, "Confirm untrusted text (user input, web pages, uploaded documents, emails) can't steer the model into privileged actions.",
                      "Keep untrusted content in user-role turns, require confirmation for irreversible tool calls, and never build SQL, shell, or URLs straight from model output.")

    def scan_ai_files(self):
        """Cross-line checks for AI features.

        The two shapes that matter are (a) untrusted text interpolated into the
        instructions the model is given, and (b) the model's output flowing into
        something that executes. Both span several lines, so a line-oriented rule
        misses them; both are severe enough to be worth a dedicated pass.
        """
        LLM = re.compile(r"(?i)(openai|anthropic|OpenAI\(|ChatOpenAI|generativeai|generateText|streamText|"
                         r"chat\.completions|messages\.create|bedrock|@ai-sdk|langchain|ollama|groq|mistralai)")
        PROMPT_INTERP = re.compile(
            r"(?i)((system|instructions?|prompt|content)\s*[:=]\s*f?['\"`][^'\"`\n]{0,400}(\{|\$\{)|"
            r"role['\"]?\s*[:=]\s*['\"]system['\"][^\n]{0,120}(f['\"]|\$\{|\+\s*\w))")
        EXECUTES = re.compile(
            r"(?i)(\.(execute|executemany|rpc|raw|\$queryRawUnsafe|\$executeRawUnsafe)\s*\(|subprocess\.|os\.system|"
            r"child_process|\beval\s*\(|\bexec\s*\(|new Function\(|\.query\s*\(\s*[`'\"])")
        for rel, abspath, ext in self.files:
            if ext not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".py", ".rb", ".go", ".php"}:
                continue
            if re.search(r"(?i)(^|/)(components|ui|hooks|stores?)/|['\"]use client['\"]", (self.text(rel, abspath) or "")[:200] + rel):
                continue
            body = self.text(rel, abspath) or ""
            if not LLM.search(body):
                continue
            m = PROMPT_INTERP.search(body)
            if m:
                line = body[:m.start()].count("\n") + 1
                self.add(40, "AI-PROMPT-INTERP", "Prompt or system instructions built by interpolation",
                         "high", "medium", rel, line, redact(m.group(0)[:160]),
                         "Put untrusted text in a user-role message with clear delimiters, keep the system prompt static, "
                         "and treat whatever comes back as untrusted data rather than instructions.")
            m2 = EXECUTES.search(body)
            if m2:
                line = body[:m2.start()].count("\n") + 1
                self.add(41, "AI-OUTPUT-EXECUTED", "File calls a model and also executes queries/commands -- check the model's output is not what runs",
                         "critical", "low", rel, line, redact(m2.group(0)[:120]),
                         "Never let model output become SQL, shell, or a URL. Constrain it to parameters in a template you wrote, "
                         "and scope every data access to the calling user.")

    def scan_history_content(self):
        """Optional deep pass: grep the full diff history for high-signal secret shapes."""
        patterns = [
            ("AKIA[0-9A-Z]{16}", "AWS access key"),
            ("sk_live_[0-9a-zA-Z]{16,}", "Stripe live key"),
            ("sk-ant-[A-Za-z0-9_-]{20,}", "Anthropic key"),
            ("ghp_[A-Za-z0-9]{20,}", "GitHub token"),
            ("-----BEGIN [A-Z ]*PRIVATE KEY", "private key"),
            ("AIza[0-9A-Za-z_-]{35}", "Google API key"),
        ]
        for pat, label in patterns:
            out = run_git(self.repo, "log", "--all", "-p", "-S", pat, "--pickaxe-regex",
                          "--pretty=format:%H %ad %an", "--date=short", "-n", "5", timeout=120)
            if out.strip():
                first = out.strip().splitlines()[0][:160]
                self.add(13, "GIT-HIST-SECRET-BLOB", f"{label} appears in commit history", "critical", "high",
                         "(git history)", 0, first,
                         "Rotate the credential. History is public the moment anyone has cloned or forked the repo.")

    # ---- output ----------------------------------------------------------
    def summarise(self):
        by_sev = Counter(f["severity"] for f in self.findings)
        by_cat = defaultdict(int)
        for f in self.findings:
            by_cat[f["category"]] += 1
        covered = sorted(by_cat.keys())
        return {
            "total_findings": len(self.findings),
            "by_severity": {s: by_sev.get(s, 0) for s in SEVERITY_ORDER},
            "by_confidence": dict(Counter(f["confidence"] for f in self.findings)),
            "categories_with_findings": covered,
            "categories_in_checklist": sorted({c["category"] for c in self.checklist}),
            "categories_untouched": [n for n in CATALOGUE if n not in by_cat
                                     and n not in {c["category"] for c in self.checklist}],
            "categories_clean": [n for n in CATALOGUE if n not in by_cat],
            "files_scanned": self.stats["files_scanned"],
            "suppressed_placeholder_matches": sum(self.suppressed.values()),
            "rules_at_cap": [r for r, c in self.rule_counts.items() if c >= self.per_rule_cap],
        }

    def run(self):
        self.collect()
        self.build_profile()
        self.scan_rules()
        self.scan_structure()
        self.findings.sort(key=lambda f: (sev_rank(f["severity"]),
                                          {"high": 0, "medium": 1, "low": 2}.get(f["confidence"], 3),
                                          f["category"], f["file"], f["line"]))
        return {
            "repo": self.repo,
            "profile": self.profile,
            "summary": self.summarise(),
            "findings": self.findings,
            "manual_checklist": self.checklist,
            "catalogue": {str(k): {"slug": v[0], "title": v[1], "default_severity": v[2], "verification": v[3]}
                          for k, v in CATALOGUE.items()},
        }


def to_markdown(report):
    p = report["profile"]
    s = report["summary"]
    out = []
    out.append("# Scanner output (raw -- needs triage)\n")
    out.append(f"Repo: `{report['repo']}`  \nFiles scanned: {s['files_scanned']}  \n")
    out.append("**Stack detected:** " + ", ".join(
        p["frameworks"] + p["data_layer"] + p["auth"] + p["ai"]) or "unknown")
    out.append("\n**Severity counts:** " + ", ".join(f"{k}={v}" for k, v in s["by_severity"].items() if v))
    prot = ", ".join(k for k, v in p["protections_present"].items() if v) or "none detected"
    out.append(f"\n**Protections present:** {prot}\n")
    cur = None
    for f in report["findings"]:
        key = (f["severity"], f["category"])
        if key != cur:
            cur = key
            out.append(f"\n## [{f['severity'].upper()}] #{f['category']} {f['category_title']}\n")
        loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
        out.append(f"- **{f['title']}** ({f['rule_id']}, confidence {f['confidence']}) — `{loc}`")
        if f["snippet"]:
            out.append(f"  - `{f['snippet']}`")
        out.append(f"  - Fix: {f['fix']}")
        if f["detail"]:
            out.append(f"  - Note: {f['detail']}")
    out.append("\n## Manual verification checklist\n")
    for c in report["manual_checklist"]:
        out.append(f"- [ ] **#{c['category']} {c['category_title']}** — {c['item']}\n  - How: {c['how_to_check']}")
    clean = report["summary"]["categories_clean"]
    out.append("\n## Categories with no static hits\n")
    out.append(", ".join(f"#{n} {CATALOGUE[n][1]}" for n in clean) or "none")
    out.append("\n(No hit is not the same as no risk — several categories can only be confirmed against the running system.)\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Scan a repo for common vibe-coded-app security failures.")
    ap.add_argument("repo", help="path to the repository")
    ap.add_argument("-o", "--outdir", default=None, help="where to write findings.json / findings.md")
    ap.add_argument("--deep-history", action="store_true", help="also pickaxe git history for secret shapes (slower)")
    ap.add_argument("--max-findings-per-rule", type=int, default=25)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.repo):
        print(f"error: {args.repo} is not a directory", file=sys.stderr)
        return 2

    outdir = args.outdir or os.path.join(os.getcwd(), "security-audit")
    os.makedirs(outdir, exist_ok=True)

    sc = Scanner(args.repo, outdir, args.deep_history, args.max_findings_per_rule)
    report = sc.run()

    with open(os.path.join(outdir, "findings.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(outdir, "findings.md"), "w") as fh:
        fh.write(to_markdown(report))

    if not args.quiet:
        s = report["summary"]
        print(f"scanned {s['files_scanned']} files -> {s['total_findings']} raw findings")
        print("  " + ", ".join(f"{k}: {v}" for k, v in s["by_severity"].items() if v))
        print(f"  categories with hits: {len(s['categories_with_findings'])}/50")
        print(f"  wrote {outdir}/findings.json and findings.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
