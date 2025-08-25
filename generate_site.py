import json, time, re, urllib.parse, datetime as dt, requests
from pathlib import Path
from typing import List, Optional
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup
import yaml

# -------------------------- Paths --------------------------
ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

# --------------------- HTTP Session ------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

def make_session() -> requests.Session:
    s = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry = Retry(total=3, backoff_factor=0.4, status_forcelist=[429, 500, 502, 503, 504])
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.mount("https://", HTTPAdapter(max_retries=retry))
    except Exception:
        pass
    s.headers.update(HEADERS)
    return s

SESSION = make_session()

# --------------------- Utilities ---------------------------
def normalize_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in list(q.keys()):
        lk = k.lower()
        if lk.startswith("utm_") or lk in {"ref", "refsrc", "fbclid"} or lk.startswith("_"):
            q.pop(k, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))

def strip_affiliate_params(url: str, to_strip: List[str]) -> str:
    if not to_strip:
        return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in to_strip:
        # strip by case-insensitive match
        for key in list(q.keys()):
            if key.lower() == k.lower():
                q.pop(key, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))

def apply_affiliate(url: str, rules: dict) -> str:
    if not rules:
        return url
    base = normalize_url(url)
    for key, aff in rules.items():
        if key.lower() in base.lower():
            # ensure proper concatenation
            if aff.startswith("?"):
                glue = "&" if "?" in base else "?"
                return base + glue + aff.lstrip("?")
            return base + aff
    return base

def is_merchant(host: str, merchant_domains: List[str]) -> bool:
    h = host.lower()
    for pat in merchant_domains or []:
        if pat.lower() in h:
            return True
    return False

AGG_HINTS = ("dealabs.com","go.dealabs.com","frandroid.com","phonandroid.com","clubic.com")
AFF_NET_HINTS = ("awin1.com","s.click.aliexpress.com","linksynergy","partnerize","impact.com","go.dealabs.com","adtraction","tradedoubler","effiliation")

def meta_refresh_target(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", attrs={"http-equiv": lambda x: x and x.lower() == "refresh"})
        if not tag:
            return None
        content = tag.get("content") or ""
        parts = content.split(";", 1)
        if len(parts) == 2:
            right = parts[1]
            pos = right.lower().find("url=")
            if pos >= 0:
                raw = right[pos+4:].strip()
                # remove surrounding quotes once
                if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                    raw = raw[1:-1].strip()
                return raw
        return None
    except Exception:
        return None

def http_follow(url: str, max_hops: int = 8) -> str:
    cur = url
    try:
        for _ in range(max_hops):
            r = SESSION.get(cur, allow_redirects=True, timeout=10)
            final = r.url
            # try to catch meta-refresh
            ct = (r.headers.get("Content-Type") or "").lower()
            if "text/html" in ct and r.text:
                nxt = meta_refresh_target(r.text)
                if nxt:
                    cur = urllib.parse.urljoin(final, nxt)
                    continue
            return final
        return cur
    except Exception:
        return cur

def pick_first_outbound(html: str, base_url: str, merchant_domains: List[str]) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Known CTA selectors (Pepper/Dealabs-like)
        selectors = [
            'a[data-role="thread-buy"]',
            "a.cept-dealBtn",
            'a[href*="/visit/"]',
            'a[href*="go.dealabs.com"]',
            'a[rel~="sponsored"]',
            'a[rel~="nofollow"]',
        ]
        for sel in selectors:
            a = soup.select_one(sel)
            if a and a.get("href"):
                return urllib.parse.urljoin(base_url, a["href"])
        # Fallback: any <a> pointing to affiliate nets or merchants
        for a in soup.find_all("a", href=True):
            href = urllib.parse.urljoin(base_url, a["href"])
            host = urllib.parse.urlsplit(href).netloc.lower()
            if any(h in host for h in AFF_NET_HINTS) or is_merchant(host, merchant_domains):
                return href
        return None
    except Exception:
        return None

def try_extract_from_jsonld(html: str) -> Optional[str]:
    # Some editorial pages embed offers in JSON-LD with an "url" field.
    try:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except Exception:
                continue
            if isinstance(data, dict):
                offers = data.get("offers")
                if isinstance(offers, dict):
                    u = offers.get("url") or (offers.get("seller", {}) or {}).get("url")
                    if u:
                        return u
            if isinstance(data, list):
                for obj in data:
                    if not isinstance(obj, dict): 
                        continue
                    offers = obj.get("offers")
                    if isinstance(offers, dict):
                        u = offers.get("url") or (offers.get("seller", {}) or {}).get("url")
                        if u:
                            return u
        return None
    except Exception:
        return None

def resolve_direct(url: str, merchant_domains: List[str]) -> str:
    # If already merchant: follow and return
    host = urllib.parse.urlsplit(url).netloc.lower()
    if is_merchant(host, merchant_domains):
        return http_follow(url)

    # Otherwise fetch aggregator page and try to extract outbound link(s)
    try:
        r = SESSION.get(url, timeout=10)
    except Exception:
        return http_follow(url)

    candidates: List[str] = []
    if r.ok:
        # 1) JSON-LD hint
        jurl = try_extract_from_jsonld(r.text)
        if jurl:
            candidates.append(urllib.parse.urljoin(url, jurl))
        # 2) CTA / affiliate / merchantish link
        out = pick_first_outbound(r.text, url, merchant_domains)
        if out:
            candidates.append(out)

    # Try each candidate, return first that ends on a merchant
    for c in candidates:
        final = http_follow(c)
        h = urllib.parse.urlsplit(final).netloc.lower()
        if is_merchant(h, merchant_domains):
            return final

    # Otherwise just follow the original; it might be a redirect endpoint (e.g., go.dealabs.com)
    return http_follow(url)

# --------------------- Feeds & Filters ---------------------
def parse_feed(url: str):
    fp = feedparser.parse(url)
    items = []
    for e in fp.entries:
        link = e.get("link") or e.get("id") or ""
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or e.get("description") or "").strip()
        # strip HTML tags crudely
        summary = re.sub("<[^>]+>", "", summary)[:300]
        # date
        if "published_parsed" in e and e.published_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=dt.timezone.utc)
        elif "updated_parsed" in e and e.updated_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.updated_parsed), tz=dt.timezone.utc)
        else:
            published = None
        items.append({"title": title, "link": link, "summary": summary, "published": published, "source": urllib.parse.urlsplit(url).netloc})
    return items

def human_time(ts):
    if not ts: return "date inconnue"
    # rough Paris DST
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

# --------------------- Site generation ---------------------
def main():
    cfg = yaml.safe_load((ROOT / "feeds.yaml").read_text(encoding="utf-8"))
    feeds = cfg.get("feeds", [])
    rules = cfg.get("affiliate_rules", {})
    site = cfg.get("site", {})
    filters = cfg.get("filters", {})
    opts = cfg.get("options", {}) or {}

    to_strip = (opts.get("affiliate_params_to_strip") or []) if opts.get("strip_affiliate_params") else []
    merchant_domains = [d.lower() for d in (opts.get("merchant_domains") or [])]
    items_limit = int(site.get("items_limit", 100))

    all_items = []
    for f in feeds:
        furl = f["url"] if isinstance(f, dict) else f
        try:
            for it in parse_feed(furl):
                orig = it["link"]
                # resolve to merchant
                direct = resolve_direct(orig, merchant_domains)
                link = normalize_url(direct)
                if to_strip: 
                    link = strip_affiliate_params(link, to_strip)
                link = apply_affiliate(link, rules)

                it["origin"] = orig
                it["link"] = link
                it["norm"] = normalize_url(link)
                it["published_human"] = human_time(it.get("published"))
                all_items.append(it)
        except Exception as ex:
            print(f"[warn] feed error {furl}: {ex}")

    filtered = [it for it in all_items if passes_filters(it, filters)]
    seen, unique = set(), []
    for it in sorted(filtered, key=lambda x: x.get("published") or dt.datetime(1970,1,1,tzinfo=dt.timezone.utc), reverse=True):
        if it["norm"] in seen: 
            continue
        seen.add(it["norm"])
        unique.append(it)
        if len(unique) >= items_limit: 
            break

    # Render if template exists; otherwise at least data.json
    env = Environment(loader=FileSystemLoader(str(ROOT)), autoescape=select_autoescape(["html"]))
    tpl = ROOT / "template.html"
    if tpl.exists():
        page = env.get_template("template.html").render(items=unique, site=site, now_human=human_time(dt.datetime.now(dt.timezone.utc)))
        (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "data.json").write_text(json.dumps(unique, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {len(unique)} items -> docs/index.html / data.json")

if __name__ == "__main__":
    main()
