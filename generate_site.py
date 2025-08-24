import re, time, json, urllib.parse, datetime as dt
from pathlib import Path
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape
import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True, parents=True)

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def normalize_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in list(q.keys()):
        if k.lower().startswith(("_", "utm_")) or k.lower() in {"ref", "refsrc"}:
            q.pop(k, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))

def apply_affiliate(url: str, rules: dict) -> str:
    base = normalize_url(url)
    for key, aff in (rules or {}).items():
        if key in base:
            aff_to_add = "&" + aff.lstrip("?") if "?" in aff and urllib.parse.urlsplit(base).query else aff
            return base + aff_to_add
    return base

def parse_feed(url: str):
    fp = feedparser.parse(url)
    items = []
    for e in fp.entries:
        link = e.get("link") or e.get("id") or ""
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or e.get("description") or "").strip()
        if "published_parsed" in e and e.published_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=dt.timezone.utc)
        elif "updated_parsed" in e and e.updated_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.updated_parsed), tz=dt.timezone.utc)
        else:
            published = None
        items.append({"title": title, "link": link, "summary": re.sub(r"<[^>]+>", "", summary)[:280], "published": published, "source": url})
    return items

def human_time(ts):
    if not ts: return "date inconnue"
    offset = 2 if 3 <= dt.datetime.utcnow().month <= 10 else 1
    tz = dt.timezone(dt.timedelta(hours=offset))
    return ts.astimezone(tz).strftime("%Y-%m-%d %H:%M")

def pass_filters(item, filters):
    t = (item.get("title") or "") + " " + (item.get("summary") or "")
    low = t.lower()
    inc = [k.lower() for k in (filters.get("include_keywords") or [])]
    exc = [k.lower() for k in (filters.get("exclude_keywords") or [])]
    if inc and not any(k in low for k in inc): return False
    if any(k in low for k in exc): return False
    return True

def main():
    cfg = load_yaml(ROOT / "feeds.yaml")
    rules = cfg.get("affiliate_rules", {})
    filters = cfg.get("filters", {})
    site = cfg.get("site", {})
    items_limit = int(site.get("items_limit", 100))

    all_items = []
    for f in cfg.get("feeds", []):
        url = f["url"] if isinstance(f, dict) else f
        try:
            for it in parse_feed(url):
                it["link"] = apply_affiliate(it["link"], rules)
                it["norm"] = normalize_url(it["link"])
                all_items.append(it)
        except Exception as ex:
            print("[warn]", url, ex)

    # filter + dedupe + sort
    filtered = [it for it in all_items if pass_filters(it, filters)]
    seen, unique = set(), []
    for it in sorted(filtered, key=lambda x: x.get("published") or dt.datetime(1970,1,1,tzinfo=dt.timezone.utc), reverse=True):
        if it["norm"] in seen: continue
        seen.add(it["norm"])
        it["published_human"] = human_time(it.get("published"))
        unique.append(it)
        if len(unique) >= items_limit: break

    # render
    env = Environment(loader=FileSystemLoader(str(ROOT)), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("template.html")
    html = tpl.render(items=unique, site=site, now_human=human_time(dt.datetime.now(dt.timezone.utc)))
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    import json
    (DOCS / "data.json").write_text(json.dumps(unique, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {len(unique)} items")

if __name__ == "__main__":
    main()
