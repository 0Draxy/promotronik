import os, re, json, time, urllib.parse, datetime as dt, shutil, requests
from pathlib import Path
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup
import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True, parents=True)

HEADERS = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"}

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def normalize_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in list(q.keys()):
        if k.lower().startswith(("utm_", "_")) or k.lower() in {"ref", "refsrc"}:
            q.pop(k, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))

def strip_affiliate_params(url: str, to_strip):
    if not to_strip: return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in to_strip:
        q.pop(k, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))

def apply_affiliate(url: str, rules: dict) -> str:
    if not rules: return url
    base = normalize_url(url)
    for key, aff in rules.items():
        if key in base:
            add = "&" + aff.lstrip("?") if ("?" in base and aff.startswith("?")) else aff
            return base + add
    return base

def is_merchant_host(host: str, merchant_domains: list[str]) -> bool:
    h = host.lower()
    for pat in merchant_domains or []:
        if pat.lower() in h:
            return True
    return False

AFFILIATE_HOST_HINTS = (
    "awin1.com","s.click.aliexpress.com","linksynergy.com",
    "partnerize","impact.com","go.dealabs.com","track","r.mradx"
)

def _extract_meta_refresh_target(html: str) -> str | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", attrs={"http-equiv": lambda x: x and x.lower() == "refresh"})
        if not tag: return None
        content = tag.get("content") or ""
        parts = content.split(";", 1)
        if len(parts) == 2 and "url=" in parts[1].lower():
            after = parts[1]
            pos = after.lower().find("url=")
            raw = after[pos+4:]
            t = raw.strip()
            if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
                t = t[1:-1].strip()
            return t
        return None
    except Exception:
        return None

def follow_chain(url: str, max_hops: int = 8) -> str:
    try:
        s = requests.Session()
        cur = url
        for _ in range(max_hops):
            r = s.get(cur, headers=HEADERS, allow_redirects=True, timeout=10)
            final = r.url
            if "text/html" in (r.headers.get("Content-Type") or "").lower():
                nxt = _extract_meta_refresh_target(r.text) or ""
                if nxt:
                    cur = urllib.parse.urljoin(final, nxt)
                    continue
            return final
        return cur
    except Exception:
        return url

def first_outbound_merchant_link(html: str, base_url: str, merchant_domains: list[str]) -> str | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        for sel in ['a[data-role="thread-buy"]','a.cept-dealBtn','a[href*="go.dealabs.com"]','a[href*="/visit/"]']:
            a = soup.select_one(sel)
            if a and a.get("href"):
                return urllib.parse.urljoin(base_url, a["href"])
        for a in soup.find_all("a", href=True):
            href = urllib.parse.urljoin(base_url, a["href"])
            host = urllib.parse.urlsplit(href).netloc.lower()
            if any(h in host for h in AFFILIATE_HOST_HINTS) or is_merchant_host(host, merchant_domains):
                return href
        return None
    except Exception:
        return None

def to_merchant(url: str, opts: dict) -> str:
    if not opts or not opts.get("prefer_direct_merchant"):
        return url
    mode = (opts.get("prefer_direct_mode") or "simple").lower()
    aggs = [d.lower() for d in (opts.get("aggregator_domains") or [])]
    merchs = [d.lower() for d in (opts.get("merchant_domains") or [])]
    try:
        u = urllib.parse.urlsplit(url)
        host = u.netloc.lower()
        if is_merchant_host(host, merchs):
            return follow_chain(url)
        if any(d in host for d in aggs) or mode == "aggressive":
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.ok:
                out = first_outbound_merchant_link(r.text, url, merchs)
                if out:
                    return follow_chain(out)
            return follow_chain(url)
        return url
    except Exception:
        return url

def parse_feed(url: str):
    fp = feedparser.parse(url)
    items = []
    for e in fp.entries:
        link = e.get("link") or e.get("id") or ""
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or e.get("description") or "").strip()
        summary = re.sub(r"<[^>]+>", "", summary)[:300]
        if "published_parsed" in e and e.published_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=dt.timezone.utc)
        elif "updated_parsed" in e and e.updated_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.updated_parsed), tz=dt.timezone.utc)
        else:
            published = None
        items.append({
            "title": title,
            "link": link,
            "summary": summary,
            "published": published,
            "source": urllib.parse.urlsplit(url).netloc
        })
    return items

def human_time(ts):
    if not ts: return "date inconnue"
    month = dt.datetime.utcnow().month
    offset = 2 if 3 <= month <= 10 else 1
    tz = dt.timezone(dt.timedelta(hours=offset))
    return ts.astimezone(tz).strftime("%Y-%m-%d %H:%M")

def passes_filters(item, filters):
    t = (item.get("title") or "") + " " + (item.get("summary") or "")
    t_low = t.lower()
    host = urllib.parse.urlsplit(item.get("link") or "").netloc.lower()
    inc_kw = [k.lower() for k in (filters.get("include_keywords") or [])]
    exc_kw = [k.lower() for k in (filters.get("exclude_keywords") or [])]
    inc_dom = [d.lower() for d in (filters.get("include_domains") or [])]
    exc_dom = [d.lower() for d in (filters.get("exclude_domains") or [])]
    if inc_kw and not any(k in t_low for k in inc_kw): return False
    if any(k in t_low for k in exc_kw): return False
    if inc_dom and not any(d in host for d in inc_dom): return False
    if any(d in host for d in exc_dom): return False
    return True

def copy_assets():
    src = ROOT / "assets"
    dst = DOCS / "assets"
    if src.exists():
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)

def main():
    cfg = load_yaml(ROOT / "feeds.yaml")
    feeds = cfg.get("feeds", [])
    rules = cfg.get("affiliate_rules", {})
    site = cfg.get("site", {})
    filters = cfg.get("filters", {})
    opts = cfg.get("options", {}) or {}
    to_strip = (opts.get("affiliate_params_to_strip") or []) if opts.get("strip_affiliate_params") else []
    limit = int(site.get("items_limit", 100))

    all_items = []
    for f in feeds:
        url = f["url"] if isinstance(f, dict) else f
        try:
            for it in parse_feed(url):
                orig = it["link"]
                direct = to_merchant(orig, opts)
                link = normalize_url(direct)
                if to_strip: link = strip_affiliate_params(link, to_strip)
                link = apply_affiliate(link, rules)
                it["origin"] = orig
                it["link"] = link
                it["norm"] = normalize_url(link)
                it["published_human"] = human_time(it.get("published"))
                all_items.append(it)
        except Exception as ex:
            print(f"[warn] feed error {url}: {ex}")

    filtered = [it for it in all_items if passes_filters(it, filters)]
    seen, unique = set(), []
    for it in sorted(filtered, key=lambda x: x.get("published") or dt.datetime(1970,1,1,tzinfo=dt.timezone.utc), reverse=True):
        if it["norm"] in seen: continue
        seen.add(it["norm"])
        unique.append(it)
        if len(unique) >= limit: break

    env = Environment(loader=FileSystemLoader(str(ROOT)), autoescape=select_autoescape(["html"]))
    page = env.get_template("template.html").render(items=unique, site=site, now_human=human_time(dt.datetime.now(dt.timezone.utc)))
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "data.json").write_text(json.dumps(unique, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
    copy_assets()
    print(f"[ok] {len(unique)} items -> docs/index.html / data.json")

if __name__ == "__main__":
    main()
