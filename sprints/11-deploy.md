# Sprint 11 — Deploy

**Read only this file.** ~3k tokens. Requires sprint 00.

## Goal

Static site on EU object storage behind a CDN, with correct compression and
cache headers, deployed by CI on push.

**Prerequisite:** the Scaleway side — account, buckets, API key, Edge
Services, DNS — is console clicking the AI cannot do. The human does
`reference/scaleway-setup.md` first; this sprint assumes its checklist is
complete and the five deploy secrets exist in GitHub Actions. Never ask the
user to paste secret values into the conversation — verify by name only.

## Why object storage

No server to patch, no runtime to exploit, near-zero cost, and it scales
without thought. The trade: no compute at the edge, so compression and
headers must be handled at upload time.

## Done when

- Push to `staging` deploys staging; push to `main` deploys production.
- Text assets serve gzipped with `Content-Encoding: gzip`.
- Hashed assets cache for a year; HTML revalidates.
- Staging is noindexed.

## Two environments, one workflow

`deploy-staging.yaml` and `deploy-prod.yaml` each call one reusable workflow,
differing only in environment name and bucket secret. Never let the two
diverge — a staging-only deploy path is a production bug waiting to ship.

```yaml
- name: Build
  env:
    # BaseLayout noindexes everything when this is "staging" (sprint 01).
    PUBLIC_SITE_ENV: ${{ inputs.environment }}
    WP_API_URL: ${{ vars.WP_API_URL }}   # sprint 06's content fetch
  run: npm run build
```

Node 22, `cache: npm`, `npm ci` — not `npm install`, which can silently
resolve different versions than the lockfile.

## Pre-compress at build time

Object storage cannot compress on the fly. Gzip text assets and upload them
with the matching header:

```yaml
- name: Pre-compress text assets (gzip)
  run: |
    find ./dist -type f \( \
      -name '*.html' -o -name '*.css' -o -name '*.js' -o -name '*.mjs' \
      -o -name '*.json' -o -name '*.xml' -o -name '*.svg' -o -name '*.txt' \
    \) -exec sh -c 'gzip -9 -nc "$1" > "$1.gz" && mv "$1.gz" "$1"' _ {} \;
```

The compressed file **replaces** the original, keeping its name. The object
key stays `index.html`; the encoding travels in the header. Uploading
`index.html.gz` as a separate key means serving a download prompt.

`-n` omits the timestamp, so identical content produces identical bytes and
the sync step does not re-upload unchanged files.

Binary assets — woff2, webp, jpg, png — are already compressed. Gzipping them
adds bytes and CPU.

Brotli would save another 15–20% but needs content negotiation the storage
layer cannot do. Gzip is universally supported and the right lazy choice; add
Brotli only if the CDN can negotiate it.

## Four-pass upload, split by cache policy

The whole point: hashed filenames cache forever, HTML never does.

```yaml
- name: Deploy to object storage
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.SCW_ACCESS_KEY }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.SCW_SECRET_KEY }}
  run: |
    EP="--endpoint-url https://s3.${{ secrets.SCW_REGION }}.scw.cloud"
    B="s3://${{ secrets.BUCKET_NAME }}"

    # 1. Hashed text (_astro JS/CSS): pre-gzipped, immutable for a year.
    aws s3 cp ./dist/_astro/ "$B"/_astro/ $EP --recursive \
      --exclude "*" --include "*.js" --include "*.css" \
      --content-encoding gzip \
      --cache-control "public, max-age=31536000, immutable"

    # 2. Hashed binaries (fonts, images): as-is, immutable for a year.
    aws s3 cp ./dist/_astro/ "$B"/_astro/ $EP --recursive \
      --exclude "*.js" --exclude "*.css" \
      --cache-control "public, max-age=31536000, immutable"

    # 3. Root text (HTML/XML/JSON/SVG/TXT): pre-gzipped, always revalidate.
    aws s3 cp ./dist/ "$B"/ $EP --recursive \
      --exclude "_astro/*" --exclude "*" \
      --include "*.html" --include "*.xml" --include "*.json" \
      --include "*.svg" --include "*.txt" \
      --content-encoding gzip \
      --cache-control "public, max-age=0, must-revalidate"

    # 4. Root binaries (ico/png/webp): as-is, revalidate.
    aws s3 cp ./dist/ "$B"/ $EP --recursive \
      --exclude "_astro/*" \
      --exclude "*.html" --exclude "*.xml" --exclude "*.json" \
      --exclude "*.svg" --exclude "*.txt" \
      --cache-control "public, max-age=0, must-revalidate"

    # 5. Prune deleted files. --size-only means matching files are NOT
    #    re-uploaded, so the Content-Encoding set above survives. This pass
    #    only removes objects no longer present in ./dist.
    aws s3 sync ./dist/ "$B"/ $EP --delete --size-only
```

Two subtleties worth keeping:

- **`--size-only` on the prune pass.** A default `sync` compares timestamps,
  re-uploads, and strips the `Content-Encoding` metadata set in passes 1–4.
  Users then get gzip bytes served as `text/html`, which renders as garbage.
- **`immutable` only on hashed filenames.** Astro hashes `_astro/*`, so the
  filename changes when content changes. Putting `immutable` on `index.html`
  would pin visitors to an old page until they hard-refresh.

## Verify the headers, not just the deploy

```bash
curl -sI https://www.example.com/ | grep -i -E 'content-encoding|cache-control'
# expect: content-encoding: gzip
#         cache-control: public, max-age=0, must-revalidate

curl -sI https://www.example.com/_astro/index.abc123.js | grep -i cache-control
# expect: cache-control: public, max-age=31536000, immutable
```

A successful deploy with wrong headers is the common failure. Check both.

## Redirects

`astro.config.mjs` redirects emit HTML meta-refresh pages in static mode —
they work but are slow and pass link equity poorly. For anything SEO-relevant
(a renamed page with backlinks), configure a real 301 at the CDN instead.

Also configure at the CDN: apex → www (or the reverse), and HTTP → HTTPS.
Decide once, match `site` in `astro.config.mjs`, and see
`reference/gotchas.md` about the file that disagreed.

## Build gates

Anything that must never ship broken belongs in `prebuild`, so it cannot be
forgotten:

```json
"prebuild": "node scripts/check-mirrors.mjs",
"build": "astro build",
"postbuild": "node scripts/obfuscate-emails.mjs"
```

A check that runs only when someone remembers is not a check.

## Backups

Object storage holds a build artifact and needs no backup — the repo is the
source. **WordPress does**: it holds your posts and your form submissions.
Use the WP host's automated backups (most managed hosts include them) or a
backup plugin on a schedule, kept off the WP server itself — and restore one
backup once to prove it works. An untested backup is a belief, not a backup.

## Verify

Push to `staging`, confirm the deploy, then:

```bash
curl -s https://staging.example.com/ | grep -c 'noindex'   # expect >= 1
curl -s https://www.example.com/ | grep -c 'noindex'       # expect 0
```

Report the actual header output. Stop.
