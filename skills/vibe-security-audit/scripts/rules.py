"""Regex rule table for the vibe-code security scanner.

Every rule is a dict:
  id        unique rule id
  cat       catalogue number (1-50, see catalogue.py)
  title     what the finding is called in the report
  sev       severity override (otherwise the catalogue default is used)
  conf      "high" | "medium" | "low"  -- how likely this is a true positive
  pat       regex, searched line by line (re.IGNORECASE unless `cs` is True)
  cs        case sensitive (default False)
  ext       list of file extensions this rule applies to (None = all text files)
  path_inc  regex the file path must match
  path_exc  regex the file path must NOT match
  not_pat   regex that, if present on the same line, suppresses the finding
  fix       one-line remediation hint
  why       why it matters (used when the report needs an explanation)

Confidence drives triage, not suppression: everything is reported, and the
agent reading the results decides. Regex cannot understand a codebase, so a
"low" confidence rule is a pointer for a human/agent to go look, not a verdict.
"""

# Strings that almost always mean "this is a placeholder, not a real secret".
PLACEHOLDER = r"(?i)(your[-_ ]?|example|placeholder|dummy|sample|redacted|xxxx|\.\.\.|<[a-z_ ]+>|\$\{|process\.env|os\.environ|import\.meta\.env|getenv|ENV\[|secrets\.|vault|\bfake\b|test[-_]?key|INSERT_|REPLACE_|TODO|FIXME|\*\*\*\*)"

CODE_EXT = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
            ".py", ".rb", ".php", ".go", ".java", ".cs", ".rs", ".kt", ".swift", ".ex", ".exs"]
JS_EXT = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"]
PY_EXT = [".py"]
WEB_EXT = JS_EXT + [".html", ".htm"]
CFG_EXT = [".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env",
           ".properties", ".tf", ".tfvars", ".xml", ".sh", ".bash", ".zsh", ".ps1", ".Dockerfile"]

FRONTEND_PATH = r"(^|/)(src/(app|pages|components|views|routes|features|ui)|app|pages|components|client|frontend|web|public|static)/"
SERVER_PATH = r"(^|/)(api|server|backend|routes?|controllers?|handlers?|functions|services|lambda|app/api|pages/api|src/api)(/|$)"

RULES = [

    # ---------------------------------------------------------------- 1,3,14
    # Provider-specific credential shapes. These are high confidence because
    # the token formats are distinctive enough not to collide with normal code.
    dict(id="SEC-AWS-AKID", cat=3, title="AWS access key ID in source", conf="high", cs=True,
         pat=r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b",
         fix="Rotate the key in IAM immediately, then load it from the platform's secret store.",
         why="An AWS access key in the repo gives anyone with the code the same cloud permissions the app has."),
    dict(id="SEC-AWS-SECRET", cat=3, title="AWS secret access key assignment", conf="medium",
         pat=r"aws_?secret_?access_?key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]", not_pat=PLACEHOLDER,
         fix="Rotate the key pair and move it to environment configuration."),
    dict(id="SEC-STRIPE-LIVE", cat=3, title="Live Stripe secret key", sev="critical", conf="high", cs=True,
         pat=r"\b(sk|rk)_live_[0-9a-zA-Z]{16,}",
         fix="Roll the key in the Stripe dashboard now; live keys can move real money."),
    dict(id="SEC-STRIPE-TEST", cat=3, title="Stripe test secret key committed", sev="medium", conf="high", cs=True,
         pat=r"\bsk_test_[0-9a-zA-Z]{16,}",
         fix="Test keys are lower risk but still belong in env config, not the repo."),
    dict(id="SEC-OPENAI", cat=3, title="OpenAI API key", conf="high", cs=True,
         pat=r"\bsk-(proj-)?[A-Za-z0-9_\-]{20,}",
         not_pat=r"(?i)(sk-ant-|process\.env|os\.environ|import\.meta|your|example|xxxx|\$\{)",
         fix="Revoke the key in the OpenAI dashboard and re-issue it as a server-side env var."),
    dict(id="SEC-ANTHROPIC", cat=3, title="Anthropic API key", conf="high", cs=True,
         pat=r"\bsk-ant-[A-Za-z0-9_\-]{20,}",
         fix="Revoke in the Anthropic console and move to server-side env config."),
    dict(id="SEC-GOOGLE", cat=3, title="Google API key", conf="high", cs=True,
         pat=r"\bAIza[0-9A-Za-z_\-]{35}\b",
         fix="Restrict or rotate the key in Google Cloud console; add HTTP referrer / API restrictions."),
    dict(id="SEC-GITHUB", cat=3, title="GitHub token", conf="high", cs=True,
         pat=r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}",
         fix="Revoke the token in GitHub settings; it may grant push access to private repos."),
    dict(id="SEC-SLACK", cat=3, title="Slack token or webhook", conf="high", cs=True,
         pat=r"(xox[abposr]-[0-9A-Za-z\-]{10,}|hooks\.slack\.com/services/T[0-9A-Za-z]+/B[0-9A-Za-z]+/[0-9A-Za-z]+)",
         fix="Revoke the token / regenerate the webhook URL in Slack."),
    dict(id="SEC-SENDGRID", cat=3, title="SendGrid API key", conf="high", cs=True,
         pat=r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}",
         fix="Revoke in SendGrid; a leaked mail key lets attackers send phishing as your domain."),
    dict(id="SEC-TWILIO", cat=3, title="Twilio credentials", conf="high", cs=True,
         pat=r"\bAC[0-9a-f]{32}\b|\bSK[0-9a-f]{32}\b",
         fix="Rotate the Twilio auth token; leaked SMS credentials get abused for toll fraud."),
    dict(id="SEC-PRIVKEY", cat=3, title="Private key material in repo", sev="critical", conf="high", cs=True,
         pat=r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----",
         fix="Treat the key as compromised: generate a new pair and remove this from history."),
    dict(id="SEC-SUPABASE-SRK", cat=3, title="Supabase service_role key", sev="critical", conf="high",
         pat=r"(service_?role|SUPABASE_SERVICE)[^\n]{0,60}eyJ[A-Za-z0-9_\-]{10,}\.eyJ",
         fix="The service_role key bypasses every RLS policy. Rotate it and keep it server-side only."),
    dict(id="SEC-JWT-BLOB", cat=3, title="Hardcoded JWT in source", sev="high", conf="medium", cs=True,
         pat=r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
         fix="Check what the token grants; if it is anything other than a public anon key, rotate it."),
    dict(id="SEC-GENERIC-ASSIGN", cat=3, title="Secret-looking value assigned inline", conf="low",
         pat=r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password|access[_-]?token|client[_-]?secret|private[_-]?key)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
         not_pat=PLACEHOLDER,
         fix="Confirm whether this is a live credential; if so, rotate and move it to env config."),
    dict(id="SEC-BASIC-AUTH-URL", cat=1, title="Credentials embedded in a URL", conf="high",
         pat=r"[a-z][a-z0-9+.\-]{2,}://[^/\s:'\"]+:[^@/\s'\"]{3,}@[^\s'\"/]+",
         not_pat=r"(?i)(user:pass|username:password|\$\{|process\.env|os\.environ|example\.com|localhost:\d)",
         fix="Move the credential out of the URL and into a secret; rotate it."),

    # ---------------------------------------------------------------- 1,7,42
    dict(id="DB-CONNSTR", cat=1, title="Database connection string with inline password", sev="critical", conf="high",
         pat=r"(postgres(ql)?|mysql|mongodb(\+srv)?|redis|mssql|amqp|clickhouse)://[^:\s'\"]+:[^@\s'\"]+@",
         not_pat=r"(?i)(\$\{|process\.env|os\.environ|<[a-z]|user:pass|username:password)",
         fix="Rotate the database password and inject the connection string from the environment."),
    dict(id="DB-GRANT-ALL", cat=42, title="Database GRANT ALL / superuser role", conf="high",
         pat=r"(?i)\bgrant\s+all\s+privileges\b|\balter\s+role\s+\w+\s+superuser\b|\bwith\s+superuser\b",
         fix="Give the application role only the tables and verbs it needs; keep DDL out of the app user."),
    dict(id="DB-TRUST-AUTH", cat=7, title="Database configured with trust / no authentication", conf="high",
         pat=r"(?i)(host\s+all\s+all\s+0\.0\.0\.0/0\s+trust|--auth\s*=\s*false|POSTGRES_HOST_AUTH_METHOD\s*[:=]\s*trust|ALLOW_EMPTY_PASSWORD\s*[:=]\s*['\"]?yes)",
         fix="Require password auth and bind the database to a private network."),
    dict(id="DB-PORT-PUBLIC", cat=7, title="Database port published to the host in Compose", sev="high", conf="medium",
         pat=r"^\s*-\s*['\"]?(0\.0\.0\.0:)?(5432|3306|27017|6379|9200|5984):\d+",
         ext=[".yml", ".yaml"], path_inc=r"(?i)(docker-)?compose",
         fix="Drop the host port mapping, or bind it to 127.0.0.1, so the DB is not reachable from the internet."),
    dict(id="DB-MONGO-OPEN", cat=7, title="MongoDB bound to all interfaces", conf="medium",
         pat=r"(?i)bind_ip\s*[:=]\s*0\.0\.0\.0|bindIp:\s*0\.0\.0\.0",
         fix="Bind to localhost or a private interface and enable authentication."),

    # ---------------------------------------------------------------- 2
    dict(id="ENV-PUBLIC-PREFIX", cat=14, title="Server secret exposed through a public build-time prefix",
         sev="critical", conf="high",
         pat=r"\b(NEXT_PUBLIC_|VITE_|REACT_APP_|PUBLIC_|EXPO_PUBLIC_|NUXT_PUBLIC_|GATSBY_)[A-Z0-9_]*(SECRET|PRIVATE|SERVICE_ROLE|PASSWORD|TOKEN|API_KEY|APIKEY|ACCESS_KEY|WEBHOOK)",
         not_pat=r"(?i)(PUBLISHABLE|ANON_KEY|_PUBLIC_KEY\b)",
         fix="Anything with a public prefix is compiled into the browser bundle. Move it to a server-only variable and rotate it."),
    dict(id="ENV-CLIENT-READ", cat=14, title="Secret-looking env var read inside client code", sev="high", conf="low",
         pat=r"(process\.env|import\.meta\.env)\.[A-Z0-9_]*(SECRET|PRIVATE_KEY|SERVICE_ROLE|PASSWORD|ACCESS_KEY)",
         ext=JS_EXT, path_inc=FRONTEND_PATH, path_exc=r"(^|/)(pages/api|app/api|api|server)/",
         fix="Confirm whether this module ships to the browser; if it does, move the logic server-side."),

    # ---------------------------------------------------------------- 8 BaaS
    dict(id="FB-RULES-OPEN", cat=8, title="Firebase rule allows unauthenticated read/write", sev="critical", conf="high",
         pat=r"allow\s+(read|write|create|update|delete)[^:;\n]*:\s*if\s+true",
         fix="Replace `if true` with a rule that checks request.auth and document ownership."),
    dict(id="FB-RULES-AUTH-ONLY", cat=8, title="Firebase rule only checks that the user is signed in", sev="high", conf="medium",
         pat=r"allow\s+(read|write|create|update|delete)[^:;\n]*:\s*if\s+request\.auth\s*!=\s*null\s*;",
         fix="Signed-in is not the same as authorised. Also compare request.auth.uid to the document's owner field."),
    dict(id="FB-RTDB-OPEN", cat=8, title="Firebase Realtime Database open to the world", sev="critical", conf="high",
         pat=r"\"\.(read|write)\"\s*:\s*true",
         fix="Scope the rule to `auth != null && auth.uid === $uid` or tighter."),
    dict(id="SB-RLS-DISABLE", cat=8, title="Row Level Security disabled on a table", sev="critical", conf="high",
         pat=r"(?i)alter\s+table[^\n;]*disable\s+row\s+level\s+security",
         fix="Re-enable RLS and write policies; without it the anon key can read the whole table."),
    dict(id="SB-POLICY-TRUE", cat=8, title="Supabase policy with an always-true predicate", sev="critical", conf="high",
         pat=r"(?i)create\s+policy[^;]{0,200}?using\s*\(\s*true\s*\)",
         fix="Compare auth.uid() to the row's owner column instead of `using (true)`."),
    dict(id="SB-SERVICE-CLIENT", cat=8, title="Supabase client created with the service role key in shared code",
         sev="critical", conf="medium", ext=JS_EXT,
         pat=r"createClient\s*\([^)]*SERVICE_ROLE",
         fix="Only instantiate the service-role client inside server-only modules that never reach the bundle."),
    dict(id="S3-PUBLIC-ACL", cat=8, title="S3 bucket or object made public", sev="critical", conf="high",
         pat=r"(?i)(acl\s*[:=]\s*['\"]?public-read(-write)?|['\"]PublicRead['\"]|BlockPublicAcls\s*[:=]\s*false|IgnorePublicAcls\s*[:=]\s*false|RestrictPublicBuckets\s*[:=]\s*false|BlockPublicPolicy\s*[:=]\s*false)",
         fix="Turn public access block back on and serve files through signed URLs or a CDN."),
    dict(id="IAM-WILDCARD", cat=8, title="Wildcard principal or action in an IAM/bucket policy", sev="high", conf="medium",
         pat=r"\"(Principal|Action|Resource)\"\s*:\s*(\"\*\"|\{\s*\"AWS\"\s*:\s*\"\*\"\s*\})",
         fix="Name the specific principals, actions, and ARNs the app actually needs."),

    # ---------------------------------------------------------------- 4,9,5
    dict(id="AUTH-EXPRESS-ADMIN", cat=9, title="Admin route with no auth middleware", sev="critical", conf="medium",
         ext=JS_EXT,
         pat=r"\b(app|router)\.(get|post|put|patch|delete|all)\s*\(\s*['\"`][^'\"`]*admin[^'\"`]*['\"`]\s*,\s*(async\s*)?\(?\s*(req|_req)",
         fix="Put an authentication + role check middleware before the handler, not inside it."),
    dict(id="AUTH-NEXT-ADMIN", once_per_file=True, cat=9, title="Admin API route handler without a session check", sev="critical", conf="low",
         ext=JS_EXT, path_inc=r"(app|pages)/api/.*admin",
         pat=r"export\s+(default\s+)?(async\s+)?function|export\s+const\s+(GET|POST|PUT|PATCH|DELETE)",
         fix="Read the session server-side at the top of the handler and reject non-admins before doing any work."),
    dict(id="AUTH-DISABLED", cat=4, title="Authentication explicitly disabled or bypassed", sev="critical", conf="medium",
         pat=r"(?i)(auth(entication)?\s*[:=]\s*(false|none|['\"]none['\"])|requireAuth\s*[:=]\s*false|skip[_-]?auth\s*[:=]\s*true|DISABLE_AUTH|BYPASS_AUTH|NO_AUTH\s*[:=]\s*(true|1))",
         fix="Remove the bypass, or gate it behind a local-development-only guard that cannot be set in production."),
    dict(id="AUTH-TODO", cat=4, title="Auth left as a TODO", sev="high", conf="medium",
         pat=r"(?i)(//|#|/\*)\s*(todo|fixme|hack|xxx)[^\n]{0,80}(auth|login|permission|security|protect|rbac|access control)",
         fix="Unfinished auth is the single most common way a vibe-coded app gets breached. Close it before launch."),
    dict(id="AUTH-WEAK-COMPARE", cat=4, title="Password or token compared with ==", sev="high", conf="medium",
         pat=r"(?i)(password|token|secret|apikey|api_key)\s*(===?|\.equals\(|==)\s*(req|request|body|params|query|headers|input)",
         fix="Hash passwords with bcrypt/argon2 and compare with the library's verify; use a timing-safe compare for tokens."),
    dict(id="AUTH-PLAINTEXT-PW", cat=49, title="Password stored or compared in plaintext", sev="critical", conf="medium",
         pat=r"(?i)(password\s*[:=]\s*(req\.body|request\.|body\.|data\.)\w*password|(user|row|record)(\.|\[['\"])password(['\"]\])?\s*===?\s*|insert[^\n]{0,60}password[^\n]{0,40}\)\s*values)",
         not_pat=r"(?i)(bcrypt|argon|scrypt|pbkdf|hash)",
         fix="Never store a recoverable password. Hash with argon2id or bcrypt (cost >= 12) at write time."),
    dict(id="CRYPTO-WEAK-HASH", cat=49, title="Weak hash used for passwords", sev="high", conf="medium",
         pat=r"(?i)(md5|sha1|sha256)\s*\(\s*[^)]{0,40}(password|passwd|pwd)",
         fix="Use argon2id or bcrypt. Fast hashes are brute-forced at billions of guesses per second."),
    dict(id="CRYPTO-WEAK-RANDOM", cat=26, title="Predictable randomness used for a security value", sev="high", conf="medium",
         pat=r"(?i)(Math\.random\(\)|random\.randint|random\.choice|rand\(\))[^\n]{0,60}(token|secret|otp|code|reset|session|nonce|password|id)",
         fix="Use crypto.randomBytes / secrets.token_urlsafe for anything an attacker must not guess."),

    # ---------------------------------------------------------------- 5,6,34,35,50
    dict(id="IDOR-PARAM-QUERY", once_per_file=True, cat=34, title="Record fetched by a client-supplied id with no ownership filter",
         sev="critical", conf="low", ext=CODE_EXT,
         pat=r"(findById|findOne|findUnique|findFirst|get\(|retrieve\()\s*\(?\s*\{?\s*[^)\n]{0,60}(req\.(params|query|body)|request\.(args|json|params)|params\.)",
         not_pat=r"(?i)(user_?id|owner|tenant|org(anization)?_?id|account_?id|session|auth)",
         fix="Add the caller's id to the where-clause: `where: { id, userId: session.user.id }`."),
    dict(id="IDOR-EQ-ID", once_per_file=True, cat=34, title="Row selected by a client-supplied id with no owner/tenant filter",
         sev="critical", conf="medium",
         pat=r"\.eq\s*\(\s*['\"]id['\"]\s*,",
         not_pat=r"(?i)(user_?id|owner|tenant|org_?id|account_?id|auth\.uid)",
         fix="Chain the owner/tenant column into the same query: `.eq(\"id\", x).eq(\"org_id\", current_org)` -- or enforce it with RLS."),
    dict(id="IDOR-SQL-ID", once_per_file=True, cat=34, title="SQL select by client id without an owner predicate", sev="critical", conf="low",
         pat=r"(?i)select\s+.{0,80}\s+from\s+\w+\s+where\s+id\s*=\s*[\$\?%:][\w\d{]",
         not_pat=r"(?i)(user_?id|owner|tenant|org(anization)?_?id|account_?id)",
         fix="Every row lookup in a multi-user app needs a tenant/owner column in the WHERE clause."),
    dict(id="AUTHZ-ROLE-FROM-CLIENT", cat=35, title="Role or permission read from the request body", sev="critical", conf="high",
         pat=r"(?i)(req\.body|request\.(json|form|data|args|values)|body|payload|data)(\s*\.\s*get\s*\(\s*['\"]|[\.\[]['\"]?)(role|is_?admin|isAdmin|permissions?|plan|tier|is_?pro|subscription|credits|balance)",
         fix="Never trust a role sent by the client. Look it up from the session or database on every request."),
    dict(id="AUTHZ-USERID-FROM-CLIENT", cat=6, title="User identity taken from client input instead of the session",
         sev="critical", conf="medium",
         pat=r"(?i)(const|let|var|)\s*\w*(userId|user_id|accountId|customerId|tenantId|orgId)\s*=\s*(req\.(body|query|params)|request\.(args|json|form)|searchParams\.get)",
         fix="Derive the user id from the verified session/JWT, never from a parameter the caller controls."),
    dict(id="TENANT-NO-SCOPE", once_per_file=True, cat=50, title="Query on a tenant-scoped table without a tenant filter", sev="critical", conf="low",
         pat=r"(?i)\.(findMany|findAll|find|select)\s*\(\s*(\{\s*\}|\)|\{\s*(take|limit|orderBy|order|include|select))",
         ext=JS_EXT, path_inc=SERVER_PATH,
         fix="In a multi-tenant app an unfiltered list query returns every tenant's rows. Always scope by org/tenant id."),

    # ---------------------------------------------------------------- 17 SQLi
    dict(id="SQLI-TEMPLATE", cat=17, title="SQL built with a template literal containing user input", sev="critical", conf="high",
         ext=JS_EXT,
         pat=r"(?i)(query|execute|raw|unsafe|\$queryRawUnsafe|\$executeRawUnsafe)\s*\(\s*`[^`]*\$\{",
         fix="Use parameterised queries ($1/?) or the ORM's safe builder; never interpolate into SQL."),
    dict(id="SQLI-CONCAT", cat=17, title="SQL built by string concatenation", sev="critical", conf="medium",
         pat=r"(?i)(select|insert\s+into|update|delete\s+from)\s+[^'\";\n]{0,80}['\"]\s*(\+|\.|%|,)\s*(req|request|params|input|user|body|query|args|name|id|email)",
         fix="Switch to bound parameters. This pattern is directly exploitable."),
    dict(id="SQLI-PY-FORMAT", cat=17, title="SQL formatted with f-string or % in Python", sev="critical", conf="high",
         ext=PY_EXT,
         pat=r"(?i)(execute|executemany|raw|text)\s*\(\s*(f['\"]|['\"][^'\"]*%s?['\"]\s*%|['\"][^'\"]*\{\w*\}[^'\"]*['\"]\s*\.format)",
         fix="Pass parameters as the second argument to execute() instead of formatting them into the string."),
    dict(id="SQLI-PRISMA-RAW", cat=17, title="Prisma raw query helper in use", sev="high", conf="low", ext=JS_EXT,
         pat=r"\$(queryRawUnsafe|executeRawUnsafe)",
         fix="Prefer $queryRaw with tagged-template parameters; the Unsafe variants do no escaping."),

    # ---------------------------------------------------------------- 18 NoSQLi
    dict(id="NOSQLI-DIRECT-BODY", cat=18, title="Request body passed straight into a Mongo query", sev="critical", conf="medium",
         ext=JS_EXT,
         pat=r"\.(find|findOne|findOneAndUpdate|updateOne|updateMany|deleteOne|deleteMany|count(Documents)?)\s*\(\s*(req\.(body|query|params)|request\.(body|query))\s*[,)]",
         fix="An attacker can send {\"$gt\":\"\"} and match every document. Whitelist fields and cast types first."),
    dict(id="NOSQLI-WHERE", cat=18, title="$where / mapReduce with dynamic content", sev="critical", conf="high",
         pat=r"\$where\s*[:=]|\bmapReduce\s*\(",
         fix="$where executes JavaScript inside the database. Rewrite it as a normal query."),

    # ---------------------------------------------------------------- 19 XSS
    dict(id="XSS-DANGEROUS-HTML", cat=19, title="dangerouslySetInnerHTML with dynamic content", conf="medium", ext=JS_EXT,
         pat=r"dangerouslySetInnerHTML\s*=\s*\{\{\s*__html\s*:\s*(?!['\"`])",
         fix="Sanitise with DOMPurify, or render as text. React escapes by default -- this opts out of that."),
    dict(id="XSS-INNERHTML", cat=19, title="innerHTML / outerHTML assigned a dynamic value", conf="medium", ext=WEB_EXT,
         pat=r"\.(inner|outer)HTML\s*(\+)?=\s*(?!['\"`]\s*['\"`])[^;\n]*(\$\{|\+|data|res|response|input|value|params|user)",
         fix="Use textContent, or sanitise the HTML before assigning it."),
    dict(id="XSS-VHTML", cat=19, title="Vue v-html directive", conf="medium", ext=[".vue", ".html"],
         pat=r"v-html\s*=",
         fix="v-html bypasses Vue's escaping. Sanitise the value or render it as text."),
    dict(id="XSS-JINJA-SAFE", cat=19, title="Template autoescaping bypassed", conf="medium",
         ext=[".html", ".jinja", ".jinja2", ".j2", ".twig", ".erb", ".py"],
         pat=r"(\|\s*safe\b|mark_safe\s*\(|autoescape\s*[:=]\s*False|raw\s*\(|<%==)",
         fix="Only mark content safe after sanitising it, and never for user-supplied strings."),
    dict(id="XSS-RENDER-STRING", cat=19, title="Template rendered from a dynamic string", sev="critical", conf="high",
         pat=r"render_template_string\s*\(|Template\s*\(\s*(request|req|user|input)",
         fix="Server-side template injection usually escalates to remote code execution. Render a fixed template file."),
    dict(id="XSS-DOC-WRITE", cat=19, title="document.write with dynamic content", conf="medium", ext=WEB_EXT,
         pat=r"document\.write(ln)?\s*\(\s*[^'\"\)]",
         fix="Build DOM nodes instead; document.write injects raw HTML."),

    # ---------------------------------------------------------------- 21 deserialization / eval
    dict(id="EVAL-USER-INPUT", cat=21, title="eval / exec on dynamic input", sev="critical", conf="high",
         pat=r"\b(eval|exec|execSync|Function|system|popen|child_process\.exec)\s*\(\s*(?!['\"`])[^)\n]{0,60}(req|request|input|body|params|query|user|argv|data)",
         fix="This is remote code execution if the value is attacker-controlled. Replace with an explicit parser or allowlist."),
    dict(id="DESER-PICKLE", cat=21, title="Unsafe deserialization", sev="critical", conf="high",
         pat=r"(pickle\.loads?|yaml\.load\s*\((?![^)]*Loader\s*=\s*(yaml\.)?(Safe|CSafe))|marshal\.loads|jsonpickle\.decode|unserialize\s*\(|ObjectInputStream)",
         fix="Use JSON, or yaml.safe_load. Deserializing untrusted data can execute code."),

    # ---------------------------------------------------------------- 22,23 upload / traversal
    dict(id="UPLOAD-NO-LIMIT", cat=22, title="File upload configured without size or type limits", conf="medium", ext=JS_EXT,
         pat=r"multer\s*\(\s*\{?[^)]{0,120}\)",
         not_pat=r"(?i)(fileFilter|limits)",
         fix="Set limits.fileSize and a fileFilter allowlist, and store uploads outside the web root."),
    dict(id="UPLOAD-ANY-TYPE", once_per_file=True, cat=22, title="Upload handler accepts any content type", conf="low",
         pat=r"(?i)(accept\s*=\s*['\"]\*/\*|mimetype\s*[:=]\s*['\"]?\*|allowedTypes\s*[:=]\s*\[\s*\])",
         fix="Allowlist extensions AND verify magic bytes; never trust the client's content-type."),
    dict(id="TRAVERSAL-JOIN", cat=23, title="Filesystem path built from request input", sev="high", conf="medium",
         pat=r"(path\.join|path\.resolve|os\.path\.join|File\s*\(|open\s*\(|readFile(Sync)?\s*\(|createReadStream\s*\()[^)\n]{0,80}(req\.(params|query|body)|request\.(args|json|params|form)|params\.|filename|filepath)",
         not_pat=r"(?i)(basename|sanitize|allowlist|whitelist|__dirname\s*,\s*['\"][\w./-]+['\"]\s*\))",
         fix="Normalise the resolved path and verify it still starts with the intended base directory; strip '..'."),
    dict(id="TRAVERSAL-SENDFILE", cat=23, title="File served from a user-supplied name", sev="high", conf="medium",
         pat=r"(sendFile|send_file|download|res\.sendfile)\s*\([^)\n]{0,60}(req\.|request\.|params|query)",
         fix="Map the request to an id, look the real path up server-side, and never echo user paths to the filesystem."),

    # ---------------------------------------------------------------- 24 SSRF
    dict(id="SSRF-FETCH", cat=24, title="Outbound request to a user-controlled URL", sev="high", conf="medium",
         path_exc=r"(?i)(^|/)(components|ui|hooks|stores?|styles)/|\.(client|browser)\.[jt]sx?$|\.tsx$",
         pat=r"\b(fetch|axios(\.(get|post|put|delete))?|requests\.(get|post|put|delete)|urlopen|got|superagent|HttpClient|curl_setopt)\s*\(\s*(?!['\"`])[^)\n]{0,60}(req\.(body|query|params)|request\.(args|json|form)|url|target|endpoint|webhook|callback|image_?url)",
         not_pat=r"(?i)(process\.env|import\.meta|BASE_URL|API_URL|localhost)",
         fix="Allowlist the hosts you will call, block private/link-local IP ranges, and disable redirects."),

    # ---------------------------------------------------------------- 25,26,27 sessions & tokens
    dict(id="JWT-HARDCODED-SECRET", cat=27, title="JWT signing secret hardcoded", sev="critical", conf="high",
         pat=r"(?i)(jwt[_-]?secret|jwt[_-]?key|token[_-]?secret|JWT_SIGNING)\s*[:=]\s*['\"][^'\"]{4,}['\"]",
         not_pat=PLACEHOLDER,
         fix="Rotate the secret, store it in env config, and force every existing session to re-authenticate."),
    dict(id="JWT-WEAK-SECRET", cat=27, title="Trivially guessable JWT/session secret", sev="critical", conf="high",
         pat=r"(?i)(secret|jwt_secret|session_secret|SECRET_KEY|SECRET_TOKEN)\s*[:=]\s*['\"]?(secret|password|changeme|mysecret|supersecret|test|dev|dev-secret|123456|key|abc123|jwt|token|secretkey|keyboard cat)['\"]?\s*$",
         fix="Generate 32+ random bytes. A guessable signing key means anyone can mint an admin token."),
    dict(id="JWT-ALG-NONE", cat=27, title="JWT verification weakened", sev="critical", conf="high",
         pat=r"(?i)(algorithms?\s*[:=]\s*\[?\s*['\"]none['\"]|verify_signature\s*[:=]\s*False|ignoreExpiration\s*[:=]\s*true|verify\s*[:=]\s*False)",
         fix="Pin the algorithm to the one you sign with and always verify signature and expiry."),
    dict(id="JWT-DECODE-NO-VERIFY", cat=27, title="JWT decoded without verifying the signature", sev="critical", conf="medium",
         pat=r"(jwt|jose)?\.?\bdecode\s*\(\s*(token|jwt|authHeader|req\.headers|bearer)",
         not_pat=r"(?i)(verify|jwt\.verify|jwtVerify)",
         fix="decode() only parses. Use verify()/jwtVerify() or anyone can hand you a forged token."),
    dict(id="SESSION-NO-EXPIRY", cat=26, title="Token or session with no expiry", sev="high", conf="medium",
         pat=r"(?i)(expiresIn\s*[:=]\s*['\"]?(never|0|100y|365d|10y)|maxAge\s*[:=]\s*(null|0|Infinity)|exp\s*[:=]\s*None)",
         fix="Give sessions a short lifetime and refresh them; long-lived tokens cannot be revoked in practice."),
    dict(id="SESSION-NO-ROTATE", once_per_file=True, cat=26, title="Session not regenerated after login", sev="medium", conf="low",
         pat=r"(?i)(req\.session\.\w+\s*=\s*|login\s*\()",
         path_inc=r"(?i)(login|signin|auth)",
         not_pat=r"(?i)(regenerate|rotate|cycleKey)",
         fix="Call session.regenerate() on privilege change to prevent session fixation."),
    dict(id="RESET-TOKEN-WEAK", cat=25, title="Password reset token generated or handled weakly", sev="high", conf="medium",
         pat=r"(?i)(reset[_-]?token|resetToken|verification[_-]?code)\s*[:=]\s*(Math\.random|uuid|Date\.now|str\(|random\.)",
         fix="Use a 32-byte cryptographic random token, hash it at rest, expire it in ~15 minutes, and single-use it."),
    dict(id="RESET-EMAIL-ONLY", cat=25, title="Password changed using only an identifier from the request", sev="critical", conf="low",
         pat=r"(?i)((update|set)[^\n]{0,80}password[^\n]{0,80}(where|by|\.eq\()[^\n]{0,40}(email|username|user_?id)|update\s*\(\s*\{\s*['\"]password['\"][^\n]{0,60}\.eq\s*\(\s*['\"](email|username)['\"])",
         fix="Require a valid, unexpired, single-use reset token -- not just an email address in the body."),

    # ---------------------------------------------------------------- 28 CORS
    dict(id="CORS-WILDCARD", cat=28, title="CORS allows any origin", conf="high",
         pat=r"(?i)(Access-Control-Allow-Origin['\"]?\s*[,:=]\s*['\"]\*|origin\s*[:=]\s*['\"]\*|origin\s*[:=]\s*true|cors\(\s*\)|allow_origins\s*=\s*\[\s*['\"]\*)",
         fix="List the exact origins you serve. `*` plus cookies is the classic account-takeover setup."),
    dict(id="CORS-REFLECT", cat=28, title="CORS origin reflected from the request", sev="critical", conf="high",
         pat=r"(?i)Access-Control-Allow-Origin[^\n]{0,40}(req\.headers|request\.headers|origin\b)",
         not_pat=r"(?i)(allowlist|whitelist|includes\(|indexOf\(|in\s+ALLOWED)",
         fix="Reflecting Origin defeats CORS entirely. Check it against an allowlist first."),
    dict(id="CORS-CREDS-WILDCARD", cat=28, title="CORS credentials enabled alongside a permissive origin", sev="critical", conf="medium",
         pat=r"(?i)(credentials\s*[:=]\s*true|allow_credentials\s*=\s*True)",
         fix="Only send credentials to an explicitly allowlisted origin."),

    # ---------------------------------------------------------------- 20 CSRF
    dict(id="CSRF-DISABLED", cat=20, title="CSRF protection disabled", sev="high", conf="high",
         pat=r"(?i)(csrf\s*[:=]\s*(false|off|None)|csrf_exempt|CSRFProtect\s*=\s*False|WTF_CSRF_ENABLED\s*=\s*False|@csrf\.exempt|csrfPrevention\s*:\s*false)",
         fix="Keep CSRF tokens on cookie-authenticated state-changing routes, or move to non-cookie auth."),
    dict(id="CSRF-SAMESITE-NONE", cat=48, title="Cookie SameSite set to none", sev="high", conf="high",
         pat=r"(?i)sameSite\s*[:=]\s*['\"]?none",
         fix="SameSite=None needs a strong reason plus Secure and CSRF tokens. Prefer Lax or Strict."),

    # ---------------------------------------------------------------- 48 cookies
    dict(id="COOKIE-HTTPONLY-FALSE", cat=48, title="Cookie explicitly readable by JavaScript", sev="high", conf="high",
         pat=r"(?i)httpOnly\s*[:=]\s*false|httponly\s*=\s*False",
         fix="Session cookies must be HttpOnly so an XSS bug cannot steal them."),
    dict(id="COOKIE-SECURE-FALSE", cat=48, title="Cookie Secure flag disabled", conf="high",
         pat=r"(?i)secure\s*[:=]\s*false(?![a-z])",
         path_exc=r"(?i)(test|spec|mock|fixture)",
         fix="Set Secure so the cookie never travels over plain HTTP."),
    dict(id="COOKIE-TOKEN-IN-STORAGE", cat=26, title="Auth token stored in localStorage", sev="high", conf="medium",
         ext=JS_EXT,
         pat=r"(localStorage|sessionStorage)\.setItem\s*\(\s*['\"][^'\"]*(token|jwt|auth|session|key|credential)",
         fix="localStorage is readable by any script on the page. Prefer an HttpOnly, Secure, SameSite cookie."),
    dict(id="COOKIE-SET-NO-FLAGS", cat=48, title="Cookie set without security flags", conf="low",
         once_per_file=True,
         pat=r"(res\.cookie\s*\(|set_cookie\s*\(|document\.cookie\s*=|['\"]Set-Cookie['\"]\s*[,:]|cookies\(\)\.set\s*\()",
         not_pat=r"(?i)(httponly)",
         fix="Add HttpOnly, Secure and SameSite to every session or auth cookie."),

    # ---------------------------------------------------------------- 10,12,37 debug & errors
    dict(id="DEBUG-TRUE", cat=10, title="Debug mode enabled", sev="high", conf="high",
         pat=r"(?i)((^|[^\w.])(DEBUG|APP_DEBUG|FLASK_DEBUG|DJANGO_DEBUG)\s*[:=]\s*(True|true|1|['\"]?on)|\[['\"]DEBUG['\"]\]\s*=\s*True|app\.run\([^)]*debug\s*=\s*True|app\.debug\s*=\s*True|DEBUG\s*=\s*os\.environ)",
         fix="Debug mode prints stack traces and, in Flask/Werkzeug, can expose an interactive console. Force it off in production."),
    dict(id="DEBUG-ALLOWED-HOSTS", cat=10, title="Django ALLOWED_HOSTS wide open", conf="high", ext=PY_EXT,
         pat=r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]",
         fix="List your real hostnames so Host-header attacks and stray probes are rejected."),
    dict(id="DEBUG-ROUTE", once_per_file=True, cat=10, title="Debug / introspection route defined", sev="high", conf="medium",
         pat=r"['\"`]/(debug|__debug__|_debug|test|dev|internal|phpinfo|env|config|status|actuator|metrics)(/[^'\"`]*)?['\"`]\s*,",
         path_inc=SERVER_PATH,
         fix="Remove it, or require an authenticated admin session and block it at the edge."),
    dict(id="DEBUG-GRAPHQL", cat=10, title="GraphQL introspection / playground enabled", conf="medium",
         pat=r"(?i)(introspection\s*[:=]\s*true|playground\s*[:=]\s*true|graphiql\s*[:=]\s*true)",
         fix="Disable introspection and the playground in production builds."),
    dict(id="ERR-STACK-TO-CLIENT", cat=12, title="Stack trace or raw error returned to the client", conf="high",
         pat=r"(res|response)\.(status\(\d+\))?\.?(json|send|write)\s*\(\s*\{?[^)\n]{0,60}(err(or)?\.(stack|message)|traceback|e\.stack)",
         fix="Log the detail server-side and return a generic message plus a correlation id."),
    dict(id="ERR-TRACEBACK-PRINT", cat=12, title="Traceback rendered into the response", conf="medium", ext=PY_EXT,
         pat=r"(traceback\.format_exc\(\)|str\(e\))[^\n]{0,40}(return|jsonify|Response|render)",
         fix="Return a generic error body; keep the traceback in the logs."),
    dict(id="SOURCEMAP-PROD", cat=37, title="Source maps enabled for production builds", conf="high",
         pat=r"(?i)(productionBrowserSourceMaps\s*:\s*true|devtool\s*:\s*['\"](source-map|eval-source-map|inline-source-map)['\"]|sourcemap\s*:\s*true|GENERATE_SOURCEMAP\s*=\s*true)",
         fix="Ship source maps to your error tracker with an upload step, not to the public bundle directory."),

    # ---------------------------------------------------------------- 11 CI / build logs
    dict(id="CI-SECRET-ECHO", cat=11, title="Secret echoed or printed in CI", sev="high", conf="medium",
         path_inc=r"(?i)(\.github/workflows|\.gitlab-ci|azure-pipelines|bitbucket-pipelines|Jenkinsfile|\.circleci)",
         pat=r"(?i)(echo|print|console\.log|cat)\s[^\n]{0,60}(secrets\.|\$\{\{\s*secrets|env\.[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD))",
         fix="Never echo secrets; CI logs are often readable by anyone with repo access, and forks can leak them."),
    dict(id="CI-PR-TARGET", cat=11, title="pull_request_target workflow (secrets exposed to fork PRs)", sev="high", conf="medium",
         path_inc=r"(?i)\.github/workflows",
         pat=r"pull_request_target",
         fix="Do not check out and run untrusted PR code in a workflow that has access to secrets."),
    dict(id="CI-ENV-DUMP", cat=11, title="Environment dumped in a build step", sev="high", conf="medium",
         pat=r"(?i)^\s*(-\s*)?(run:\s*)?(env|printenv|set)\s*$|npm\s+config\s+ls\s+-l",
         path_inc=r"(?i)(\.github/workflows|\.gitlab-ci|Dockerfile|Makefile)",
         fix="Remove the dump; it writes every secret into the build log."),
    dict(id="DOCKER-SECRET-ARG", cat=11, title="Secret passed as a Docker build ARG/ENV", sev="high", conf="medium",
         path_inc=r"(?i)dockerfile",
         pat=r"(?i)^\s*(ARG|ENV)\s+\w*(SECRET|TOKEN|PASSWORD|API_?KEY|ACCESS_KEY)",
         fix="Build args persist in image layers. Use BuildKit secret mounts or inject at runtime."),

    # ---------------------------------------------------------------- 15,33 client-side trust
    dict(id="CLIENT-ROLE-GATE", cat=15, title="Authorization decided in client-side code", sev="high", conf="low",
         ext=JS_EXT, path_inc=FRONTEND_PATH, path_exc=r"(^|/)(pages/api|app/api|api|server)/",
         once_per_file=True,
         pat=r"(?i)(\.(isAdmin|is_admin|isPro|is_pro|isPremium|hasAccess|canEdit|permissions)\b|\.(role|plan|tier)\s*===?\s*['\"](admin|owner|superuser|moderator|pro|premium|paid|enterprise)['\"])",
         fix="Client checks are UX only. Re-check the same rule in the API handler that touches the data."),
    dict(id="PAY-CLIENT-PRICE", cat=33, title="Price or amount originating from the client", sev="critical", conf="medium",
         pat=r"(?i)['\"]?(amount|price|unit_amount|total|quantity|currency_amount)['\"]?\s*[:=]\s*[^,;\n]{0,40}(req\.body|request\.(json|form|args)|body|payload|params|data)\s*(\[|\.get\s*\(|\.)\s*['\"]?(amount|price|unit_amount|total|quantity)",
         fix="Look the price up server-side from your own catalogue; never charge what the browser says."),
    dict(id="PAY-CLIENT-ENTITLEMENT", cat=33, title="Subscription/entitlement state read from client storage", sev="critical", conf="medium",
         ext=JS_EXT,
         pat=r"(localStorage|sessionStorage|cookies?)\.(getItem|get)\s*\(\s*['\"][^'\"]*(pro|premium|plan|subscri|paid|credits|entitle)",
         fix="Entitlements must be checked server-side against your billing records on every gated request."),

    # ---------------------------------------------------------------- 32 webhooks
    dict(id="WEBHOOK-NO-VERIFY", once_per_file=True, cat=32, title="Webhook endpoint without signature verification", sev="high", conf="medium",
         pat=r"['\"`][^'\"`]*/(webhook|webhooks|callback|hooks)[^'\"`]*['\"`]",
         path_inc=SERVER_PATH,
         fix="Verify the provider's signature header (e.g. stripe.webhooks.constructEvent) over the raw body before trusting the payload."),
    dict(id="WEBHOOK-STRIPE-UNSAFE", cat=32, title="Stripe webhook parsed without constructEvent", sev="critical", conf="medium",
         ext=JS_EXT, path_inc=r"(?i)(webhook|stripe)",
         pat=r"(JSON\.parse\s*\(\s*req\.body|req\.body\.type\s*===)",
         not_pat=r"constructEvent",
         fix="Use stripe.webhooks.constructEvent with the raw body and STRIPE_WEBHOOK_SECRET."),

    # ---------------------------------------------------------------- 29 rate limits
    dict(id="RATE-LIMIT-OFF", cat=29, title="Rate limiting explicitly disabled or unbounded", conf="medium",
         pat=r"(?i)(rate_?limit\s*[:=]\s*(false|none|0|null)|max\s*[:=]\s*(Infinity|0)\s*,\s*windowMs|skip\s*:\s*\(\)\s*=>\s*true)",
         fix="Rate limit login, signup, password reset, and any endpoint that costs you money per call."),

    # ---------------------------------------------------------------- 31 default creds
    dict(id="DEFAULT-CREDS", cat=31, title="Default or placeholder credentials in config", sev="critical", conf="medium",
         pat=r"(?i)(password|passwd|pwd|pass)\s*[:=]\s*['\"]?(admin|password|passw0rd|root|test|123456|12345678|changeme|letmein|secret|guest|postgres|mysql|toor|default)['\"]?\s*$",
         fix="Replace with a generated secret. Default credentials are the first thing scanners try."),
    dict(id="DEFAULT-ADMIN-SEED", cat=31, title="Seeded admin account with a known password", sev="critical", conf="medium",
         pat=r"(?i)(admin@|username\s*[:=]\s*['\"]admin['\"])[^\n]{0,80}(password|pass)\s*[:=]\s*['\"][^'\"]{1,20}['\"]",
         fix="Seed accounts with a random password printed once, or require a first-run setup flow."),

    # ---------------------------------------------------------------- 36 logging
    dict(id="LOG-SENSITIVE", cat=36, title="Sensitive value written to logs", conf="medium",
         pat=r"(console\.(log|info|warn|error|debug)|print\s*\(|logger?\.(info|debug|warn|error)|fmt\.Print)[^\n]{0,80}\b(password|passwd|token|jwt|secret|api_?key|authorization|credit_?card|ssn|cvv)\b",
         not_pat=r"(?i)(redact|mask|\*\*\*|hasPassword|missing|invalid|error:)",
         fix="Redact these fields before logging. Logs get shipped to third parties and kept for months."),
    dict(id="LOG-REQ-DUMP", cat=36, title="Whole request body or headers logged", conf="medium",
         pat=r"(console\.log|print|logger?\.\w+)\s*\(\s*[^)\n]{0,30}(req\.(body|headers)|request\.(headers|json|form)|JSON\.stringify\(req)",
         fix="Log a whitelist of fields; bodies and headers routinely contain tokens and personal data."),

    # ---------------------------------------------------------------- 16 validation
    dict(id="VALIDATE-SPREAD-BODY", cat=16, title="Request body spread directly into a database write", sev="high", conf="medium",
         ext=JS_EXT,
         pat=r"(create|update|insert|save|set)\s*\(\s*\{?\s*(\.\.\.)?\s*(data\s*:\s*)?(\.\.\.)?(req\.body|request\.body|body)\s*[,}\)]",
         fix="Parse the body through a schema (zod/valibot/pydantic) and pick fields explicitly -- mass assignment lets callers set role, plan, or ownership columns."),
    dict(id="VALIDATE-PARSEINT-RAW", once_per_file=True, cat=16, title="Unvalidated numeric/query input used directly", conf="low",
         pat=r"(parseInt|parseFloat|Number|int|float)\s*\(\s*(req\.(query|params|body)|request\.args)",
         fix="Validate ranges after parsing; NaN and huge values cause surprising behaviour downstream."),

    # ---------------------------------------------------------------- 40,41 AI
    dict(id="AI-PROMPT-CONCAT", cat=40, title="User input concatenated into a prompt", sev="high", conf="medium",
         pat=r"(?i)(system|systemPrompt|instructions|prompt|messages)\s*[:=][^\n]{0,80}(\$\{|\+\s*|f['\"])[^\n]{0,60}(req\.|request\.|input|userInput|user_message|body\.|query\.)",
         fix="Keep user text in a clearly delimited user turn, never inside the system prompt, and validate the model's output before acting on it."),
    dict(id="AI-TOOL-NO-AUTHZ", cat=41, title="AI tool/function definition -- check it enforces the caller's permissions",
         sev="high", conf="low", once_per_file=True,
         pat=r"(?i)(tools\s*[:=]\s*[\{\[]|@tool\b|\btool\s*\(\s*\{|def\s+\w+_tool\s*\(|function_declarations|tool_choice)",
         path_inc=SERVER_PATH,
         fix="Run every tool call through the same authorization layer as a normal request, scoped to the calling user."),
    dict(id="AI-SQL-FROM-MODEL", cat=41, title="Model output executed as code or SQL", sev="critical", conf="medium",
         pat=r"(?i)(execute|query|eval|exec|run)\s*\(\s*[^)\n]{0,50}(completion|response|choices\[0\]|message\.content|llm|model_?output|ai_?response)",
         fix="Never execute model output directly. Constrain it to a parameterised template you built."),
    dict(id="AI-NO-RATE-LIMIT", once_per_file=True, cat=29, title="AI endpoint with no visible spend control", conf="low",
         pat=r"(?i)(openai|anthropic|/v1/(chat/)?completions|generateContent|bedrock)",
         path_inc=SERVER_PATH,
         not_pat=r"(?i)(ratelimit|rate_limit|quota|throttle|credits)",
         fix="Add per-user rate limits and a spend cap; an unmetered AI endpoint is a direct route to a large bill."),

    # ---------------------------------------------------------------- 46 dashboards
    dict(id="DASH-EXPOSED", once_per_file=True, cat=46, title="Internal dashboard or admin tool exposed", sev="high", conf="medium",
         pat=r"(?i)(adminer|phpmyadmin|prisma\s+studio|pgadmin|redis-?commander|mongo-?express|kibana|grafana|traefik.*dashboard|swagger-?ui|bull-?board)",
         fix="Keep these off the public internet: bind to localhost, use a VPN or SSO proxy."),

    # ---------------------------------------------------------------- 47 headers
    dict(id="HEADER-CSP-UNSAFE", cat=47, title="Content-Security-Policy weakened", conf="medium",
         pat=r"(?i)(unsafe-inline|unsafe-eval|default-src\s+\*|script-src[^;'\"]*\*)",
         fix="Remove unsafe-inline/unsafe-eval; use nonces or hashes so a CSP actually stops XSS."),
    dict(id="HEADER-TLS-DISABLED", cat=49, title="TLS certificate verification disabled", sev="critical", conf="high",
         pat=r"(?i)(rejectUnauthorized\s*[:=]\s*false|verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*[:=]\s*['\"]?0|InsecureSkipVerify\s*:\s*true|curl_setopt[^\n]*SSL_VERIFYPEER[^\n]*false)",
         fix="Fix the certificate chain instead. Disabling verification makes TLS decorative."),
    dict(id="HTTP-INSECURE-URL", once_per_file=True, cat=49, title="Plain HTTP used for an external call", sev="medium", conf="low",
         pat=r"['\"]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|www\.w3\.org|schemas\.|purl\.org|xmlns|ns\.adobe)[a-z0-9.\-]+\.[a-z]{2,}",
         fix="Use HTTPS; plain HTTP exposes tokens and data in transit."),

    dict(id="JWT-SIGN-LITERAL", cat=27, title="JWT signed with an inline string literal", sev="critical", conf="high",
         pat=r"(jwt|jose)?\.?\bsign\s*\([^)\n]{0,120},\s*['\"][^'\"]{1,64}['\"]",
         not_pat=r"(?i)(process\.env|os\.environ|import\.meta|config\.|settings\.)",
         fix="Load the signing key from configuration and make it at least 32 random bytes."),
    dict(id="EVAL-ANY", once_per_file=True, cat=21, title="Dynamic code execution present", sev="high", conf="low",
         pat=r"(?<![\w.])(eval|exec)\s*\(",
         path_exc=r"(?i)(node_modules|\.min\.js|test|spec)",
         fix="Check where the argument comes from. If any part of it is user-influenced this is remote code execution."),

    # ---------------------------------------------------------------- 43 audit logs
    dict(id="AUDIT-DESTRUCTIVE-NOLOG", once_per_file=True, cat=43, title="Destructive database operation with no audit trail", conf="low",
         path_inc=SERVER_PATH,
         pat=r"(\.(deleteMany|deleteOne|destroyAll|truncate)\s*\(|\b(DROP\s+TABLE|TRUNCATE\s+TABLE|DELETE\s+FROM)\b|\.delete\s*\(\s*\{)",
         fix="Record who did what and when for destructive and privilege-changing actions."),
]


def compile_rules():
    import re
    out = []
    for r in RULES:
        flags = 0 if r.get("cs") else re.IGNORECASE
        try:
            r = dict(r)
            r["_re"] = re.compile(r["pat"], flags)
            r["_not"] = re.compile(r["not_pat"], re.IGNORECASE) if r.get("not_pat") else None
            r["_pinc"] = re.compile(r["path_inc"], re.IGNORECASE) if r.get("path_inc") else None
            r["_pexc"] = re.compile(r["path_exc"], re.IGNORECASE) if r.get("path_exc") else None
            out.append(r)
        except re.error as exc:  # a broken rule must never take the whole scan down
            print("rule {} failed to compile: {}".format(r.get("id"), exc))
    return out
