#!/usr/bin/env python3
"""Self-test for the scanner. Run after changing rules.py or scan.py.

Builds a throwaway vulnerable repo in a temp directory, scans it, and asserts
that each probe line produces the expected rule. Also scans a deliberately clean
repo and asserts zero findings, which is what stops rules drifting into noise.

    python3 selftest.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# (filename, content, expected rule ids that must fire somewhere in the scan)
PROBES = [
    ("server/keys.js", # key split so secret scanners do not flag this source file; the fixture the
     # test writes at runtime still contains the joined shape the rule needs.
     'const k = "AKIAIOSFODNN7EXAMPLE";\nconst s = "' + "sk_live_" + '51H8xQ2LkdIwHu7ixaBcDeFgH";\n',
     ["SEC-AWS-AKID", "SEC-STRIPE-LIVE"]),
    ("server/db.js", 'const c = "postgresql://app:hunter2@db.host:5432/prod";\n'
                     'const r = await db.query(`SELECT * FROM u WHERE id = ${req.params.id}`);\n',
     ["DB-CONNSTR", "SQLI-TEMPLATE"]),
    ("server/api/notes.js", 'app.get("/api/admin/all", (req, res) => { res.json(db.query("SELECT * FROM notes")) });\n'
                            'const u = await User.findOne(req.body);\n'
                            'const role = req.body.role;\n',
     ["AUTH-EXPRESS-ADMIN", "NOSQLI-DIRECT-BODY", "AUTHZ-ROLE-FROM-CLIENT"]),
    ("server/http.js", 'app.use(cors({ origin: "*", credentials: true }));\n'
                       'res.cookie("s", t, { httpOnly: false, sameSite: "none" });\n'
                       'res.status(500).json({ error: err.stack });\n',
     ["CORS-WILDCARD", "COOKIE-HTTPONLY-FALSE", "CSRF-SAMESITE-NONE", "ERR-STACK-TO-CLIENT"]),
    ("server/tokens.js", 'const t = jwt.sign({ id }, "secret");\nconst d = jwt.decode(req.headers.authorization);\n'
                         'const resetToken = Math.random().toString(36);\n',
     ["JWT-SIGN-LITERAL", "JWT-DECODE-NO-VERIFY", "RESET-TOKEN-WEAK"]),
    ("app/page.tsx", 'export default function P({u}){ return <div dangerouslySetInnerHTML={{__html: u.bio}} /> }\n',
     ["XSS-DANGEROUS-HTML"]),
    ("api/files.py", 'import pickle\n'
                     'data = pickle.loads(request.data)\n'
                     'open(os.path.join(BASE, request.args.get("f")))\n'
                     'requests.get(request.args.get("url"))\n'
                     'DEBUG = True\n',
     ["DESER-PICKLE", "TRAVERSAL-JOIN", "SSRF-FETCH", "DEBUG-TRUE"]),
    ("firestore.rules", 'match /{d=**} { allow read, write: if true; }\n', ["FB-RULES-OPEN"]),
    ("supabase/migrations/1.sql", 'create table docs (id uuid, user_id uuid);\ngrant all privileges on docs to anon;\n',
     ["SB-RLS-MISSING", "DB-GRANT-ALL"]),
    (".github/workflows/ci.yml", 'jobs:\n  b:\n    steps:\n      - run: echo "${{ secrets.API_KEY }}"\n',
     ["CI-SECRET-ECHO"]),
    (".env", 'DATABASE_URL=postgresql://app:hunter2@db.host:5432/prod\nJWT_SECRET=secret\n',
     ["ENV-TRACKED", "JWT-WEAK-SECRET"]),
    ("next.config.js", 'module.exports = { productionBrowserSourceMaps: true }\n', ["SOURCEMAP-PROD"]),
    ("docker-compose.yml", 'services:\n  db:\n    environment:\n      POSTGRES_PASSWORD: postgres\n    ports:\n      - "5432:5432"\n',
     ["DEFAULT-CREDS", "DB-PORT-PUBLIC"]),
]

CLEAN = [
    (".gitignore", "node_modules\n.env\n.env.*\n!.env.example\n"),
    (".env.example", "DATABASE_URL=your-database-url-here\n"),
    ("package.json", json.dumps({"name": "clean", "dependencies": {
        "next": "14.2.5", "zod": "3.23.8", "next-auth": "4.24.7", "@prisma/client": "5.16.1",
        "helmet": "7.1.0", "@upstash/ratelimit": "2.0.1", "bcryptjs": "2.4.3", "@sentry/nextjs": "8.20.0"}})),
    ("package-lock.json", '{"lockfileVersion":3}'),
    ("app/api/notes/route.ts",
     'import { getServerSession } from "next-auth";\nimport { z } from "zod";\n'
     'const B = z.object({ title: z.string().max(200) });\n'
     'export async function GET() {\n'
     '  const session = await getServerSession();\n'
     '  if (!session?.user) return new Response("Unauthorized", { status: 401 });\n'
     '  return Response.json(await prisma.note.findMany({ where: { userId: session.user.id } }));\n}\n'),
    ("next.config.js",
     'module.exports = { async headers() { return [{ source: "/(.*)", headers: ['
     '{ key: "Content-Security-Policy", value: "default-src \'self\'" },'
     '{ key: "Strict-Transport-Security", value: "max-age=63072000" }] }] } };\n'),
]


def build(root, files):
    for rel, content in files:
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(content)
    subprocess.run(["git", "init", "-q", root], capture_output=True)
    subprocess.run(["git", "-C", root, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], capture_output=True)


def scan(root, out):
    subprocess.run([sys.executable, os.path.join(HERE, "scan.py"), root, "-o", out, "--quiet"], check=True)
    with open(os.path.join(out, "findings.json")) as fh:
        return json.load(fh)


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        vuln = os.path.join(tmp, "vuln")
        build(vuln, [(f, c) for f, c, _ in PROBES])
        report = scan(vuln, os.path.join(tmp, "out-vuln"))
        fired = {f["rule_id"] for f in report["findings"]}
        for _, _, expected in PROBES:
            for rid in expected:
                if rid not in fired:
                    failures.append(f"MISSING: {rid} did not fire on the vulnerable fixture")
        cats = set(report["summary"]["categories_with_findings"]) | set(report["summary"]["categories_in_checklist"])
        if len(cats) < 35:
            failures.append(f"COVERAGE: only {len(cats)} of 50 categories produced output")

        clean = os.path.join(tmp, "clean")
        build(clean, CLEAN)
        creport = scan(clean, os.path.join(tmp, "out-clean"))
        if creport["findings"]:
            for f in creport["findings"]:
                failures.append(f"FALSE POSITIVE on clean fixture: {f['rule_id']} {f['file']}:{f['line']}")

    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} problem(s)")
        return 1
    print(f"selftest ok — {len(fired)} rules fired on the vulnerable fixture, "
          f"{len(cats)}/50 categories covered, 0 findings on the clean fixture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
