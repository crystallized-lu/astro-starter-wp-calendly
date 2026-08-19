# Scaleway from zero — the clicking-around part

Sprint 11 assumes a Scaleway bucket, an API key, and a CDN already exist.
This file is the part that gets you there. It is written for a human, not
the AI: **these steps happen in your browser and your AI assistant cannot
click them for you** — but after each stage there's a way for it to verify
the result.

Menu names are accurate as of mid-2026. Consoles move things around; if a
label has changed, look for the concept in bold — it will still exist.

## Rule zero: never paste secrets into the AI chat

Along the way you will generate a **secret key** and copy it somewhere.
That somewhere is **never the chat window**.

- Anything you paste to an AI assistant may be stored in conversation
  history, logs, or transcripts you don't control. A secret key that has
  been in a chat is burned, exactly as if you'd committed it to the repo.
- The AI never needs your secrets. It needs to know that a secret **exists
  and what it's called** (e.g. "SCW_SECRET_KEY is set in GitHub"). The
  value goes directly from the Scaleway page into the GitHub secrets page,
  typed or pasted by you.
- If you slip and paste one: don't delete the message and hope. Go to
  Scaleway, revoke that API key, generate a new one. Two minutes, zero
  drama, done properly.

The same rule applies to your WordPress application password and anything
labelled "secret", "token", or "private key" anywhere in this guide.

## 1. Account and project

1. Sign up at **console.scaleway.com**. You'll need a payment card and
   identity verification; a site this size typically costs a few euros a
   month.
2. Scaleway organises resources into **Projects**. The `default` project is
   fine, or create one named after your site: click the project dropdown
   (top left) → **Create project**.

## 2. Two buckets (production and staging)

A bucket is a folder in the cloud that can serve files to the internet.

1. Left sidebar → **Storage** → **Object Storage** → **Create bucket**.
2. Region: pick the one nearest your visitors — **fr-par** (Paris),
   **nl-ams** (Amsterdam), or **pl-waw** (Warsaw). Note which one; the
   deploy workflow needs its name.
3. Name it after your domain, e.g. `www-example-com`. Bucket names are
   public and global, so no secrets in the name.
4. Visibility: **Private** is fine — the CDN will read it; visitors never
   hit the bucket directly.
5. Repeat for staging: `staging-example-com`, same region.
6. On each bucket: open it → **Settings** tab → enable **Static website
   hosting** (labelled "Bucket website") → index page `index.html`, error
   page `404.html` → Save.

**Verify with your AI:** tell it the bucket names and region; it should
confirm the workflow files reference the same region string.

## 3. API key (this is the secret part)

The deploy workflow needs credentials to upload files.

1. Click your organisation name (top right) → **IAM & API keys** — or go
   directly to console.scaleway.com/iam.
2. First create an **application** (a robot user, so the key isn't tied to
   your personal login): **Applications** tab → **Create application** →
   name it `site-deployer`.
3. Give it only storage rights: **Policies** tab → **Create policy** →
   attach it to `site-deployer` → add a rule: scope = your project,
   permission set = **ObjectStorageFullAccess**. Nothing else — if this key
   ever leaks, the blast radius is your website files, not your whole
   account.
4. **API keys** tab → **Generate API key** → bearer = the `site-deployer`
   application. You get an **access key ID** (starts `SCW`, not secret) and
   a **secret key** (shown **once**, never again).
5. **Leave this browser tab open** and put the values straight into GitHub
   — next step. If you lose the secret, don't hunt for it: generate a new
   key and delete the old one.

## 4. Put the secrets into GitHub (yourself)

The deploy runs on GitHub Actions, which reads secrets from the repo's own
vault — not from your chat, not from a file in the repo.

1. On github.com, open your site's repository → **Settings** (the repo's
   settings tab, not your account) → **Secrets and variables** →
   **Actions** → **New repository secret**.
2. Create, one at a time, copying values from the Scaleway tab:

   | Name | Value |
   |---|---|
   | `SCW_ACCESS_KEY` | the access key ID |
   | `SCW_SECRET_KEY` | the secret key |
   | `SCW_REGION` | your region, e.g. `fr-par` |
   | `BUCKET_NAME` | production bucket, e.g. `www-example-com` |
   | `BUCKET_NAME_STAGING` | staging bucket |

3. Close the Scaleway tab. The secret now exists in exactly two places:
   Scaleway and GitHub's vault. That's correct.

**Verify with your AI:** say "the five deploy secrets are set in GitHub —
list the names you expect and check the workflows use them." It can verify
names without ever seeing values.

## 5. CDN and your domain (Edge Services)

The CDN is what makes the site fast worldwide and gives it HTTPS.

1. In the Scaleway console: **Storage** → **Object Storage** → your
   production bucket → **Edge Services** tab (also reachable via
   **Network** → **Edge Services**) → **Create pipeline** — this may
   require enabling the Edge Services subscription first; the console
   prompts you.
2. Origin: your production bucket.
3. **Customize domain**: enter `www.your-domain.com`. Scaleway offers a
   **managed TLS certificate** (Let's Encrypt) — take it; it renews itself.
4. The pipeline gets an endpoint like `xxxx.svc.edge.scw.cloud`. Copy it.
5. At your DNS provider (wherever you bought the domain — or Scaleway
   **Domains and DNS** if you transferred it): add a **CNAME** record:
   name `www`, value = that endpoint. Scaleway's domain-customization
   screen shows the exact record and validates it for you.
6. The bare domain (`example.com`, no www) can't take a CNAME at most
   providers. Use your registrar's **redirect** feature: permanent (301)
   redirect from `example.com` to `https://www.example.com`. If your DNS
   provider supports **ALIAS/ANAME** records, that works too, but the
   simple redirect is enough.
7. Repeat a minimal version for staging (own pipeline, subdomain
   `staging.your-domain.com`) — or skip the custom domain and use the raw
   `*.svc.edge.scw.cloud` endpoint for staging; it's not public-facing.

DNS changes take minutes to a few hours to propagate. Not broken, just slow.

**Verify with your AI:** after the first deploy, it runs the header checks
at the end of sprint 11 (`curl -sI https://www.your-domain.com/`) and
confirms HTTPS, gzip, and cache headers.

## 6. If you build sprint 08 (forms) or a booking backend

Those need one small server-side piece: **Containers** (sidebar:
**Serverless** → **Containers**) plus a managed **PostgreSQL** database
(**Databases** → **PostgreSQL**). Create them in the same project and
region. The database password is a secret — rule zero applies: it goes
from the Scaleway page into the container's **environment variables**
(container → Settings → Environment variables, mark it "secret"), never
into chat or code. Sprint 08 covers the code; the console part is just
those two creations plus copying the database hostname.

## The whole thing, as a checklist

- [ ] Scaleway account, project chosen
- [ ] Two buckets (prod + staging), website hosting enabled on both
- [ ] `site-deployer` application with storage-only policy
- [ ] API key generated; secret seen once, pasted only into GitHub
- [ ] Five secrets in GitHub Actions
- [ ] Edge Services pipeline, custom domain, managed TLS
- [ ] `www` CNAME set; apex 301-redirects to www
- [ ] First push to `staging` deploys; headers verified
- [ ] Nothing secret has ever touched the chat window
