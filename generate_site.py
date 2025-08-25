import os, json, yaml
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape
from utils.normalize import Item, dedupe
from utils.affiliates import ensure_amazon_tag
from sources.amazon_paapi import fetch_amazon_items
from sources.awin_feed import fetch_awin_feed

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

def collect_amazon(cfg):
    ac = cfg.get("amazon", {}) or {}
    if not ac.get("enabled"): 
        return []
    items = fetch_amazon_items(
        marketplace=ac.get("marketplace") or "www.amazon.fr",
        partner_tag=ac.get("partner_tag"),
        queries=ac.get("queries") or []
    )
    tag = ac.get("partner_tag") or os.getenv("AMAZON_PARTNER_TAG")
    for it in items:
        it.url = ensure_amazon_tag(it.url, tag)
    return items

def collect_awin(cfg):
    aw = cfg.get("awin", {}) or {}
    if not aw.get("enabled"):
        return []
    out = []
    for feed in aw.get("feeds") or []:
        if not feed.get("enabled"): 
            continue
        env_name = feed.get("env")
        url = os.getenv(env_name, "")
        if not url:
            print(f"[awin] {feed.get('name')} → no URL in env {env_name}, skipped")
            continue
        out.extend(fetch_awin_feed(url, feed.get("name")))
    min_disc = float(aw.get("min_discount_percent") or 0)
    if min_disc:
        out = [it for it in out if it.old_price and it.price and it.old_price > it.price and (it.old_price - it.price)/it.old_price*100.0 >= min_disc]
    return out

def rank_items(items, cfg):
    rk = cfg.get("ranking", {}) or {}
    prefer = rk.get("prefer_merchants") or []
    w_disc = float(rk.get("weight_discount") or 0.6)
    w_rec  = float(rk.get("weight_recency_hours") or 0.4)

    now = datetime.now(timezone.utc)
    def score(it: Item):
        d = 0.0
        if it.old_price and it.price and it.old_price > it.price:
            d = (it.old_price - it.price) / it.old_price * 100.0
        d = max(0.0, min(d, 80.0)) / 80.0
        try:
            age_h = (now - datetime.fromisoformat(it.updated_at)).total_seconds() / 3600.0
        except Exception:
            age_h = 24.0
        r = max(0.0, 1.0 - min(age_h, 72.0)/72.0)
        mboost = 0.1 if it.merchant in prefer else 0.0
        return w_disc*d + w_rec*r + mboost

    return sorted(items, key=score, reverse=True)

def render(items, cfg):
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=select_autoescape(["html"]))
    now = datetime.now(timezone.utc)
    page = env.get_template("index.html").render(
        items=[it.to_dict() for it in items],
        site=cfg.get("site"),
        updated_at=now.isoformat()
    )
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "data.json").write_text(json.dumps([it.to_dict() for it in items], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {len(items)} items → docs/")

def main():
    cfg = load_config()
    items = []
    items += collect_amazon(cfg)
    items += collect_awin(cfg)
    items = dedupe(items)
    items = rank_items(items, cfg)
    limit = int(cfg.get("site", {}).get("items_limit", 120))
    items = items[:limit]
    render(items, cfg)

if __name__ == "__main__":
    main()
