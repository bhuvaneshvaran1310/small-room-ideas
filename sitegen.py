"""Builds the whole public website (docs/) from the saved posts in data/posts/."""
import html
import json
import re
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote_plus

e = html.escape

FONTS = "https://fonts.googleapis.com/css2?family=Barlow:wght@400;500&family=Barlow+Condensed:wght@600;700&display=swap"

CSS = """:root{--bg:#E9ECE6;--ink:#1D2B2F;--muted:#55656A;--line:#C3CBC4;--accent:#2E6B5E;--on-accent:#FFFFFF}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:400 18px/1.65 "Barlow",system-ui,sans-serif}
a{color:var(--accent)}
a:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
.top{border-bottom:2px solid var(--ink);padding:14px 20px}
.brand{font:700 30px/1 "Barlow Condensed",system-ui,sans-serif;color:var(--ink);text-decoration:none}
main{max-width:720px;margin:0 auto;padding:36px 20px 64px}
h1{font:700 clamp(40px,8vw,64px)/1 "Barlow Condensed",system-ui,sans-serif;margin:0 0 14px}
h2{font:600 31px/1.1 "Barlow Condensed",system-ui,sans-serif;margin:42px 0 8px}
p{margin:0 0 16px;max-width:66ch}
.meta{color:var(--muted);font-size:16px;margin-bottom:24px}
.cover{display:block;width:100%;max-width:380px;height:auto;margin:0 0 30px;border:2px solid var(--ink)}
.intro{font-size:20px}
.shop{display:inline-block;padding:10px 16px;border:2px solid var(--accent);color:var(--accent);text-decoration:none;font-weight:500}
.shop:hover{background:var(--accent);color:var(--on-accent)}
.disclosure{margin-top:52px;padding-top:16px;border-top:2px solid var(--ink);font-size:15px;color:var(--muted)}
.list{list-style:none;padding:0;margin:28px 0 0}
.list li{display:grid;grid-template-columns:84px 1fr;gap:18px;padding:22px 0;border-top:1px solid var(--line)}
.list img{width:84px;height:126px;object-fit:cover;border:1px solid var(--ink);display:block}
.list h2{margin:0 0 4px;font-size:30px}
.list h2 a{color:var(--ink);text-decoration:none}
.list h2 a:hover{text-decoration:underline}
.list p{margin:0;color:var(--muted);font-size:16px}
footer{border-top:2px solid var(--ink);padding:18px 20px;font-size:15px;color:var(--muted)}
footer a{margin-right:18px}
"""


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60].rstrip("-") or "post"


def amazon_link(cfg, query):
    domain = cfg.get("amazon_domain", "www.amazon.in")
    return f"https://{domain}/s?k={quote_plus(query)}&tag={cfg['amazon_tag']}"


def human_date(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def disclosure_html(cfg):
    parts = [
        "<strong>As an Amazon Associate I earn from qualifying purchases.</strong>",
        "Shop links go to Amazon.in search results for the type of product discussed. "
        "Prices change often, so check the current price and details on Amazon before you buy.",
    ]
    if cfg.get("ai_disclosure", True):
        parts.append("These guides are drafted with AI assistance and reviewed by a person before they are published.")
    return " ".join(parts)


def page(cfg, *, title, desc, root, body, canonical, og_image=None, og_type="website"):
    base = cfg["base_url"].rstrip("/")
    verify = ""
    if cfg.get("pinterest_verify_code"):
        verify = f'<meta name="p:domain_verify" content="{e(cfg["pinterest_verify_code"])}">\n'
    og_img = f'<meta property="og:image" content="{e(og_image)}">\n<meta name="twitter:card" content="summary_large_image">\n' if og_image else ""
    return f"""<!doctype html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:site_name" content="{e(cfg['site_name'])}">
{og_img}{verify}<link rel="alternate" type="application/rss+xml" title="{e(cfg['site_name'])}" href="{e(base)}/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="top"><a class="brand" href="{root}index.html">{e(cfg['site_name'])}</a></header>
<main>
{body}
</main>
<footer><a href="{root}about.html">About</a><a href="{root}disclosure.html">Affiliate disclosure</a><a href="{e(base)}/feed.xml">RSS</a></footer>
</body>
</html>
"""


def render_post(cfg, post):
    base = cfg["base_url"].rstrip("/")
    slug = post["slug"]
    sections = []
    for idea in post["ideas"]:
        sections.append(
            f"<section>\n<h2>{e(idea['heading'])}</h2>\n<p>{e(idea['why_it_works'])}</p>\n"
            f'<p><a class="shop" rel="sponsored nofollow noopener" target="_blank" '
            f'href="{e(amazon_link(cfg, idea["shop_query"]))}">{e(idea["shop_label"])}</a></p>\n</section>'
        )
    body = (
        f"<article>\n<h1>{e(post['title'])}</h1>\n<p class=\"meta\">Published {human_date(post['date_iso'])}</p>\n"
        f"<img class=\"cover\" src=\"../images/{e(slug)}.jpg\" width=\"1000\" height=\"1500\" alt=\"{e(post['title'])}\">\n"
        f"<p class=\"intro\">{e(post['intro'])}</p>\n" + "\n".join(sections) +
        f"\n<p>{e(post['closing'])}</p>\n<p class=\"disclosure\">{disclosure_html(cfg)}</p>\n</article>"
    )
    return page(
        cfg, title=f"{post['title']} | {cfg['site_name']}", desc=post["meta_description"], root="../", body=body,
        canonical=f"{base}/posts/{slug}.html", og_image=f"{base}/images/{slug}.jpg", og_type="article",
    )


def render_index(cfg, posts):
    base = cfg["base_url"].rstrip("/")
    if posts:
        items = "\n".join(
            f'<li><img src="images/{e(p["slug"])}.jpg" width="84" height="126" alt="" loading="lazy">'
            f'<div><h2><a href="posts/{e(p["slug"])}.html">{e(p["title"])}</a></h2><p>{e(p["meta_description"])}</p></div></li>'
            for p in posts
        )
        listing = f'<ul class="list">\n{items}\n</ul>'
    else:
        listing = "<p>The first guide is on its way.</p>"
    body = f"<h1>{e(cfg['site_name'])}</h1>\n<p class=\"intro\">{e(cfg.get('tagline', ''))}</p>\n{listing}\n<p class=\"disclosure\">{disclosure_html(cfg)}</p>"
    return page(cfg, title=cfg["site_name"], desc=cfg.get("tagline", cfg["site_name"]), root="", body=body, canonical=f"{base}/")


def render_about(cfg):
    base = cfg["base_url"].rstrip("/")
    body = f"<h1>About</h1>\n<p>{e(cfg['about_text'])}</p>\n<p class=\"disclosure\">{disclosure_html(cfg)}</p>"
    return page(cfg, title=f"About | {cfg['site_name']}", desc=cfg["about_text"][:150], root="", body=body, canonical=f"{base}/about.html")


def render_disclosure(cfg):
    base = cfg["base_url"].rstrip("/")
    body = f"<h1>Affiliate disclosure</h1>\n<p>{disclosure_html(cfg)}</p>\n<p>If you buy through a link on this site, the price you pay does not change.</p>"
    return page(cfg, title=f"Affiliate disclosure | {cfg['site_name']}", desc="How this site earns money.", root="", body=body, canonical=f"{base}/disclosure.html")


def render_feed(cfg, posts):
    base = cfg["base_url"].rstrip("/")
    items = []
    for p in posts[:30]:
        url = f"{base}/posts/{p['slug']}.html"
        img = f"{base}/images/{p['slug']}.jpg"
        pub = format_datetime(datetime.fromisoformat(p["date_iso"]))
        items.append(
            "<item>"
            f"<title>{e(p['pin_title'])}</title><link>{e(url)}</link>"
            f'<guid isPermaLink="true">{e(url)}</guid><pubDate>{pub}</pubDate>'
            f"<description>{e(p['pin_description'])}</description>"
            f'<media:content url="{e(img)}" medium="image" type="image/jpeg" width="1000" height="1500"/>'
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"<title>{e(cfg['site_name'])}</title><link>{e(base)}/</link>"
        f"<description>{e(cfg.get('tagline', ''))}</description><language>en-in</language>\n"
        f'<atom:link href="{e(base)}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items) + "\n</channel>\n</rss>\n"
    )


def render_sitemap(cfg, posts):
    base = cfg["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/about.html", f"{base}/disclosure.html"] + [f"{base}/posts/{p['slug']}.html" for p in posts]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(
        f"<url><loc>{e(u)}</loc></url>" for u in urls) + "\n</urlset>\n"


def load_posts(root):
    posts = []
    for f in (Path(root) / "data" / "posts").glob("*.json"):
        posts.append(json.loads(f.read_text(encoding="utf-8")))
    posts.sort(key=lambda p: p["date_iso"], reverse=True)
    return posts


def unique_slug(root, title):
    base = slugify(title)
    slug, n = base, 2
    while (Path(root) / "data" / "posts" / f"{slug}.json").exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def rebuild(cfg, root):
    root = Path(root)
    docs = root / "docs"
    (docs / "posts").mkdir(parents=True, exist_ok=True)
    (docs / "images").mkdir(parents=True, exist_ok=True)
    posts = load_posts(root)
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    (docs / "style.css").write_text(CSS, encoding="utf-8")
    (docs / "index.html").write_text(render_index(cfg, posts), encoding="utf-8")
    (docs / "about.html").write_text(render_about(cfg), encoding="utf-8")
    (docs / "disclosure.html").write_text(render_disclosure(cfg), encoding="utf-8")
    for p in posts:
        (docs / "posts" / f"{p['slug']}.html").write_text(render_post(cfg, p), encoding="utf-8")
    (docs / "feed.xml").write_text(render_feed(cfg, posts), encoding="utf-8")
    (docs / "sitemap.xml").write_text(render_sitemap(cfg, posts), encoding="utf-8")
    base = cfg["base_url"].rstrip("/")
    (docs / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    return len(posts)
