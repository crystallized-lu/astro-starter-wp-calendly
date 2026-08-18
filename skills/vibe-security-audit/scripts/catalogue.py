"""Canonical catalogue of the 50 vibe-coded-app risk categories.

The numbering follows the source checklist this skill was built from. Item 21
was blank in that list; it has been filled with "Insecure deserialization",
which is the obvious neighbour of the injection items around it.

Each entry: (number, short slug, human title, default severity, whether the
category can be judged from source alone or needs live/runtime verification).

`mode` values:
  static  -> a repo scan can reach a verdict
  hybrid  -> the repo gives strong evidence, but confirm against the live system
  runtime -> the repo can only hint; a human must check the deployed system
"""

CATALOGUE = {
    1:  ("db-credentials",        "Exposed database credentials",                        "critical", "static"),
    2:  ("public-env",            "Public / committed .env files",                       "critical", "static"),
    3:  ("hardcoded-keys",        "Hardcoded API keys and tokens",                       "critical", "static"),
    4:  ("weak-auth",             "Weak or missing authentication",                      "critical", "static"),
    5:  ("no-authz",              "No authorization checks",                             "critical", "static"),
    6:  ("cross-user-data",       "Users able to access other users' data",              "critical", "static"),
    7:  ("open-db-perms",         "Open database read/write permissions",                "critical", "static"),
    8:  ("baas-misconfig",        "Misconfigured Firebase / Supabase / S3",              "critical", "hybrid"),
    9:  ("open-admin-routes",     "Admin routes left unprotected",                       "critical", "static"),
    10: ("debug-exposed",         "Debug pages / debug mode exposed in production",      "high",     "hybrid"),
    11: ("build-log-secrets",     "Build logs and CI leaking secrets",                   "high",     "hybrid"),
    12: ("verbose-errors",        "Verbose errors leaking stack traces",                 "medium",   "static"),
    13: ("git-history-leak",      "Leaked repos or secrets in commit history",           "critical", "hybrid"),
    14: ("frontend-secrets",      "Secrets bundled into frontend JavaScript",            "critical", "static"),
    15: ("client-side-checks",    "Client-side-only security checks",                    "high",     "static"),
    16: ("no-input-validation",   "Missing input validation",                            "high",     "static"),
    17: ("sqli",                  "SQL injection",                                       "critical", "static"),
    18: ("nosqli",                "NoSQL injection",                                     "critical", "static"),
    19: ("xss",                   "Cross-site scripting (XSS)",                          "high",     "static"),
    20: ("csrf",                  "Cross-site request forgery (CSRF)",                   "high",     "static"),
    21: ("insecure-deser",        "Insecure deserialization / unsafe eval",              "critical", "static"),
    22: ("insecure-upload",       "Insecure file uploads",                               "high",     "static"),
    23: ("path-traversal",        "Path traversal",                                      "high",     "static"),
    24: ("ssrf",                  "Server-side request forgery (SSRF)",                  "high",     "static"),
    25: ("password-reset",        "Broken password reset flows",                         "high",     "static"),
    26: ("session-mgmt",          "Weak session management",                             "high",     "static"),
    27: ("jwt-weak",              "Weak, leaked, or reused JWT secrets",                 "critical", "static"),
    28: ("cors",                  "Overly permissive CORS",                              "high",     "static"),
    29: ("no-rate-limit",         "Missing rate limits on auth, APIs, AI endpoints",     "high",     "static"),
    30: ("public-staging",        "Public test or staging environments",                 "high",     "runtime"),
    31: ("default-creds",         "Default credentials left unchanged",                  "critical", "static"),
    32: ("webhook-unverified",    "Webhooks without signature verification",             "high",     "static"),
    33: ("frontend-payments",     "Payment / subscription checks only on the frontend",  "critical", "static"),
    34: ("idor",                  "Insecure direct object references (IDOR)",            "critical", "static"),
    35: ("trusted-client-ids",    "APIs trusting user-controlled IDs or roles",          "critical", "static"),
    36: ("log-pii",               "Logs containing tokens, emails, passwords, PII",      "medium",   "static"),
    37: ("source-maps",           "Source maps exposed in production",                   "medium",   "hybrid"),
    38: ("dep-vulns",             "Dependency vulnerabilities",                          "high",     "hybrid"),
    39: ("outdated-packages",     "Outdated / unpinned packages",                        "medium",   "hybrid"),
    40: ("prompt-injection",      "Prompt injection in AI features",                     "high",     "static"),
    41: ("ai-tool-perms",         "AI tools acting on data without permission checks",   "critical", "static"),
    42: ("db-user-perms",         "Excessive database permissions for the app user",     "high",     "hybrid"),
    43: ("no-audit-logs",         "No audit logs",                                       "medium",   "hybrid"),
    44: ("no-monitoring",         "No monitoring or alerting",                           "medium",   "runtime"),
    45: ("no-backups",            "No backup or restore plan",                           "high",     "runtime"),
    46: ("public-dashboards",     "Publicly exposed internal dashboards",                "high",     "hybrid"),
    47: ("missing-headers",       "Missing security headers",                            "medium",   "hybrid"),
    48: ("cookie-flags",          "Cookies missing HttpOnly / Secure / SameSite",        "high",     "static"),
    49: ("unencrypted-data",      "Unencrypted sensitive data",                          "high",     "static"),
    50: ("tenant-isolation",      "Poor tenant isolation in multi-user apps",            "critical", "static"),
}

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def title(num):
    return CATALOGUE[num][2]


def slug(num):
    return CATALOGUE[num][1]


def default_severity(num):
    return CATALOGUE[num][3]


def mode(num):
    return CATALOGUE[num][4]
