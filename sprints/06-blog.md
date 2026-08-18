# Sprint 06 — Blog (headless WordPress)

**Read only this file.** ~3k tokens. Requires sprint 01.

## Goal

A blog authored in WordPress and rendered by Astro. Posts are fetched from
the WP REST API **at build time** through a content loader, so everything
downstream — layout, archive, RSS, related posts — uses the normal
`getCollection('blog')` API and ships as static HTML. WordPress never serves
a public page.

## Done when

- `/blog/` lists posts newest first; `/blog/<slug>/` renders one.
- `/blog/rss.xml` validates.
- Publishing in WP + rebuilding the site shows the new post. No WP URL
  appears anywhere in the built site.
- Cards in a row are equal height regardless of description length.

## Loader — `src/content.config.ts`

```ts
import { defineCollection, z } from 'astro:content';

const WP_API = process.env.WP_API_URL; // e.g. https://cms.example.com/wp-json/wp/v2

const blog = defineCollection({
  loader: {
    name: 'wp-posts',
    load: async ({ store, parseData }) => {
      store.clear();
      let page = 1;
      while (true) {
        const res = await fetch(
          `${WP_API}/posts?status=publish&per_page=100&page=${page}&_embed`
        );
        if (!res.ok) {
          if (res.status === 400) break; // WP returns 400 past the last page
          throw new Error(`WP API ${res.status} — refusing to build a partial blog`);
        }
        const posts = await res.json();
        if (posts.length === 0) break;
        for (const p of posts) {
          const media = p._embedded?.['wp:featuredmedia']?.[0];
          const data = await parseData({
            id: p.slug,
            data: {
              title: p.title.rendered,
              description: p.excerpt.rendered.replace(/<[^>]+>/g, '').trim(),
              author: p._embedded?.author?.[0]?.name ?? 'Author Name',
              date: p.date_gmt + 'Z',
              updated: p.modified_gmt + 'Z',
              readTime: p.acf?.read_time ?? '5 min',
              featuredImage: media?.source_url ?? '/images/blog-fallback.jpg',
              featuredImageAlt: media?.alt_text ?? '',
            },
          });
          store.set({ id: p.slug, data, rendered: { html: p.content.rendered } });
        }
        page += 1;
      }
    },
  },
  schema: z.object({
    title: z.string(),
    description: z.string(),
    author: z.string(),
    date: z.coerce.date(),
    updated: z.coerce.date(),
    readTime: z.string(),
    featuredImage: z.string(),
    featuredImageAlt: z.string().default(''),
    // Filled by the heading-ID pass below.
    headings: z.array(z.object({
      depth: z.number(), slug: z.string(), text: z.string(),
    })).default([]),
  }),
});

export const collections = { blog };
```

Notes that matter:

- **Fail closed.** A non-OK response throws and kills the build. A partial
  fetch that silently ships half the archive is worse than no deploy.
- **`per_page=100` is WP's hard maximum** — hence the pagination loop. A
  single unpaged fetch works until post #101, then silently truncates.
- **`date_gmt + 'Z'`**, not `date`. WP's plain `date` field is in the site's
  local timezone with no offset marker; parsing it as UTC shifts every
  publish date.
- **`readTime` comes from an ACF (or similar) custom field**, hand-written by
  the author. A word-count estimate is wrong for posts with code blocks or
  diagrams. If you skip the custom field, the fallback is honest enough.
- The sprint-05 AEO payload (faq/mentions/citations) can ride along the same
  way — ACF repeater fields mapped into the loader. Add them when you do
  sprint 05, not before.

Because the loader stores `rendered.html`, `render(post)` works downstream
exactly as it would for markdown — templates do not know WordPress exists.

## Heading IDs and the table of contents

WP's block editor emits `<h2>` without `id` attributes, so anchors and a TOC
need them injected. Do it once, in the loader, before `store.set`:

```ts
const headings = [];
const html = p.content.rendered.replace(
  /<h2([^>]*)>(.*?)<\/h2>/g,
  (_, attrs, text) => {
    const plain = text.replace(/<[^>]+>/g, '').trim();
    const slug = plain.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
    headings.push({ depth: 2, slug, text: plain });
    return `<h2${attrs} id="${slug}">${text}</h2>`;
  }
);
// pass headings via data, html via rendered
```

A regex over your own CMS's predictable output is fine here; reach for an
HTML parser only if posts start embedding exotic markup.

TOC rules: **H2 only** — H3s make long posts unnavigable rather than more
navigable. Show it at 3+ sections; shorter posts read fine without one.

```astro
{showToc && (
  <nav aria-label="In this post">
    <p>In this post</p>
    <ol>{tocItems.map((h) => <li><a href={`#${h.slug}`}>{h.text}</a></li>)}</ol>
  </nav>
)}
```

## Trust boundary

`content.rendered` is raw HTML injected into your pages. With a single
trusted author that is acceptable. The moment WP has multiple authors,
contributors, or any plugin that writes post content, sanitize at load time
(`sanitize-html`, allowlist of tags) — an XSS in a post body is an XSS on
your whole site.

Also strip or rewrite any absolute URLs pointing at the WP host: images
should be re-hosted or proxied, and internal links must point at the Astro
site, or you leak the CMS domain and slow every post load.

## Dynamic route

```astro
---
import { getCollection, render } from 'astro:content';
import BlogLayout from '../../layouts/BlogLayout.astro';

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  return posts.map((post) => ({ params: { slug: post.id }, props: { post } }));
}

const { post } = Astro.props;
const { Content } = await render(post);

// Related posts: three most recent, excluding this one. No tags, no
// similarity scoring. On a blog under ~50 posts recency beats relevance
// and costs nothing to maintain.
const relatedPosts = (await getCollection('blog'))
  .filter((p) => p.id !== post.id)
  .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime())
  .slice(0, 3)
  .map((p) => ({
    slug: p.id, title: p.data.title, description: p.data.description,
    readTime: p.data.readTime, featuredImage: p.data.featuredImage,
  }));
---
<BlogLayout {...post.data} headings={post.data.headings} relatedPosts={relatedPosts}>
  <Content />
</BlogLayout>
```

## Post structured data

```astro
const pageUrl = new URL(Astro.url.pathname, Astro.site).href;

const blogPostingNode = {
  '@type': 'BlogPosting',
  '@id': `${pageUrl}#blogposting`,
  headline: title,
  description,
  // By @id — stitches into the site graph instead of declaring a new author.
  author: { '@id': 'https://www.example.com/#founder' },
  publisher: { '@id': 'https://www.example.com/#organization' },
  datePublished: new Date(date).toISOString(),
  dateModified: new Date(updated).toISOString(),
  inLanguage: lang,
  image: featuredImage,
  mainEntityOfPage: { '@type': 'WebPage', '@id': pageUrl },
};
```

`dateModified` comes from WP's `modified_gmt`, which WP maintains for free —
one advantage over hand-edited frontmatter, where the source site set both
dates from the same value and a five-year-old post claimed to have been
modified the day it was written.

## Cards with equal heights

Flexbox with `flex: 1` on the description, `margin-top: auto` on the link.
No JavaScript, no fixed heights, works at any content length.

```astro
<article style="height:100%; display:flex; flex-direction:column; border:1px solid var(--border);">
  <div style="overflow:hidden; background:var(--bg); aspect-ratio:16/10;">
    <img src={post.data.featuredImage} alt={post.data.featuredImageAlt || ''}
         style="width:100%; height:100%; object-fit:cover; display:block;" loading="lazy" />
  </div>
  <div style="padding:20px 22px 22px; flex:1; display:flex; flex-direction:column;">
    <div style="font-size:0.8rem; color:var(--text-muted);">
      {formattedDate} · {post.data.readTime} read
    </div>
    <h3 style="font-family:var(--font-display); font-weight:400;">{post.data.title}</h3>
    <p style="color:var(--text-muted); flex:1;">{post.data.description}</p>
    <a href={`/blog/${post.id}/`} style="margin-top:auto; color:var(--purple); font-weight:700;">
      Read more <span aria-hidden="true">→</span>
    </a>
  </div>
</article>
```

The `aspect-ratio` box is what prevents layout shift as thumbnails load.

Build this as **one** `BlogPostCard.astro` and use it everywhere. The source
site had the component and then inlined a near-duplicate on the archive page,
so the two drifted.

## Date formatting

```astro
const formattedDate = new Date(date).toLocaleDateString(
  lang === 'fr' ? 'fr-FR' : 'en-GB',
  { year: 'numeric', month: 'long', day: 'numeric' }
);
```

Use `en-GB` over `en-US` unless the audience is American — `20 July 2026`
rather than `July 20, 2026`.

## RSS

```ts
import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('blog'))
    .sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime());

  return rss({
    title: 'Blog',
    description: '…',
    site: context.site,
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: new Date(post.data.date),
      link: `/blog/${post.id}/`,
      author: post.data.author,
    })),
    customData: '<language>en-gb</language>',
    stylesheet: '/rss/styles.xsl',
  });
}
```

The `stylesheet` makes the feed render as a readable page in a browser
instead of an XML error wall. Cheap, and it stops people thinking it is
broken. Do **not** expose WP's own `/feed/` — it advertises the CMS host.

## Rebuild on publish

A static site only shows what existed at build time. Wire a WP webhook
(plugin: "WP Webhooks", or a 10-line mu-plugin on `publish_post`) to your CI
build hook. Until that exists, "publish" means "publish, then trigger a
build by hand" — fine for a solo blog, infuriating for anyone else.

## Verify

```bash
npm run build
curl -s http://localhost:4321/blog/rss.xml | head -5
grep -ri "cms\." dist/ | head        # expect nothing — no CMS URLs in output
```

Publish a test post in WP, rebuild, confirm it appears. Load the archive with
descriptions of very different lengths and confirm the cards align.

Stop. Report.
