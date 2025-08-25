import os, re, json, time, urllib.parse, datetime as dt
from pathlib import Path
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape
from slugify import slugify
import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True, parents=True)


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_url(url: str) -> str:
    # Nettoyage minimal pour dédoublonnage
    u = urllib.parse.urlsplit(url)
    # Retire trackers communs
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    for k in list(q.keys()):
        if k.lower().startswith(("_", "utm_")) or k.lower() in {"ref", "refsrc"}:
            q.pop(k, None)
    new_q = urllib.parse.urlencode(q, doseq=True)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))


def apply_affiliate(url: str, rules: dict) -> str:
    if not rules:
        return url
    base = normalize_url(url)
    for key, aff in rules.items():
        if key in base:
            # Si l'affiliation commence par "?" et qu'il y a déjà une query, remplace "?" par "&"
            if "?" in aff and urllib.parse.urlsplit(base).query:
                aff = "&" + aff.lstrip("?")
            return base + aff
    return base


def parse_feed(url: str):
    fp = feedparser.parse(url)
    items = []
    for e in fp.entries:
        link = e.get("link") or e.get("id") or ""
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or e.get("description") or "").strip()
        published = None
        if "published_parsed" in e and e.published_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.published_parsed), tz=dt.timezone.utc)
        elif "updated_parsed" in e and e.updated_parsed:
            published = dt.datetime.fromtimestamp(time.mktime(e.updated_parsed), tz=dt.timezone.utc)
        items.append({
            "title": title,
            "link": link,
            "summary": re.sub(r"<[^>]+>", "", summary)[:280],
            "published": published,
            "source": urllib.parse.urlsplit(url).netloc
        })
    return items


def human_time(ts: dt.datetime) -> str:
    if not ts:
        return "date inconnue"
    # Affichage en Europe/Paris sans dépendance externe: +2h en été approximatif
    paris = dt.timezone(dt.timedelta(hours=2))
    loc = ts.astimezone(paris)
    return loc.strftime("%Y-%m-%d %H:%M")


def main():
    cfg = load_yaml(ROOT / "feeds.yaml")
    feeds = cfg.get("feeds", [])
    rules = cfg.get("affiliate_rules", {})
    site = cfg.get("site", {})
    filters_cfg = cfg.get("filters", {})
    include_keywords = [k.lower() for k in filters_cfg.get("include_keywords", [])]
    exclude_keywords = [k.lower() for k in filters_cfg.get("exclude_keywords", [])]

    limit = int(site.get("items_limit", 100))

    all_items = []
    for f in feeds:
        url = f["url"] if isinstance(f, dict) else f
        try:
            items = parse_feed(url)
            for it in items:
                it["link"] = apply_affiliate(it["link"], rules)
                it["norm"] = normalize_url(it["link"])
                # Filtrage
                title_lower = it["title"].lower()
                summary_lower = it.get("summary", "").lower()
                combined = title_lower + " " + summary_lower
                if include_keywords and not any(kw in combined for kw in include_keywords):
                    continue
                if exclude_keywords and any(kw in combined for kw in exclude_keywords):
                    continue
                all_items.append(it)
        except Exception as ex:
            print(f"[warn] feed error {url}: {ex}")

    # Dédoublonnage par URL normalisée + tri par date
    seen = set()
    unique = []
    for it in sorted(all_items, key=lambda x: x.get("published") or dt.datetime(1970,1,1,tzinfo=dt.timezone.utc), reverse=True):
        if it["norm"] in seen:
            continue
        seen.add(it["norm"])
        it["published_human"] = human_time(it.get("published"))
        unique.append(it)
        if len(unique) >= limit:
            break

    # Rendu HTML
    env = Environment(
        loader=FileSystemLoader(str(ROOT)),
        autoescape=select_autoescape(["html"])
    )
    tpl = env.get_template("template.html")
    html = tpl.render(items=unique, site=site, now_human=human_time(dt.datetime.now(dt.timezone.utc)))
    (DOCS / "index.html").write_text(html, encoding="utf-8")

    # Export JSON (optionnel)
    (DOCS / "data.json").write_text(json.dumps(unique, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {len(unique)} items -> docs/index.html")

if __name__ == "__main__":
    main()
