from __future__ import annotations
import os
from typing import List, Optional
from amazon_paapi import AmazonApi
from utils.normalize import Item, now_iso, sanitize_text

COUNTRY_BY_HOST = {
    "www.amazon.fr": "FR",
    "www.amazon.de": "DE",
    "www.amazon.it": "IT",
    "www.amazon.es": "ES",
    "www.amazon.co.uk": "UK",
    "www.amazon.com": "US",
}

def safe_get(obj, path, default=None):
    cur = obj
    for p in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except Exception:
                return default
        else:
            cur = getattr(cur, p, None)
    return cur if cur is not None else default

def fetch_amazon_items(marketplace: str, partner_tag: Optional[str], queries: List[dict]) -> List[Item]:
    access = os.getenv("AMAZON_ACCESS_KEY")
    secret = os.getenv("AMAZON_SECRET_KEY")
    tag   = partner_tag or os.getenv("AMAZON_PARTNER_TAG")
    if not (access and secret and tag):
        print("[amazon] missing keys or partner tag → skipping")
        return []

    country = COUNTRY_BY_HOST.get(marketplace or "www.amazon.fr", "FR")
    amazon = AmazonApi(access, secret, tag, country, throttling=1)

    out: List[Item] = []
    for q in queries:
        keywords = q.get("keywords")
        sort_by = q.get("sort_by") or "SalesRank"
        min_savings = float(q.get("min_savings_percent") or 0)

        try:
            res = amazon.search_items(keywords=keywords, sort_by=sort_by)
        except Exception as e:
            print(f"[amazon] search_items error for '{keywords}': {e}")
            continue

        for it in getattr(res, "items", []) or []:
            title = sanitize_text(safe_get(it, "item_info.title.display_value"))
            url = safe_get(it, "detail_page_url")
            img = (safe_get(it, "images.primary.large.url") or 
                   safe_get(it, "images.primary.medium.url"))

            # price and old price
            price = safe_get(it, "offers.listings.0.price.amount")
            currency = safe_get(it, "offers.listings.0.price.currency")
            # try to get base price via summaries / savings
            basis = safe_get(it, "offers.summaries.0.price.amount")
            saving = safe_get(it, "offers.summaries.0.savings.amount")
            old_price = None
            if basis and saving is not None:
                try:
                    old_price = float(basis)
                    price = float(basis) - float(saving)
                except Exception:
                    pass

            if min_savings and old_price and price:
                try:
                    pct = (float(old_price) - float(price)) / float(old_price) * 100.0
                    if pct < min_savings:
                        continue
                except Exception:
                    pass

            if not (title and url):
                continue

            out.append(Item(
                title=title,
                merchant="amazon",
                url=url,
                image=img,
                price=float(price) if price is not None else None,
                old_price=float(old_price) if old_price is not None else None,
                currency=currency or "EUR",
                category=keywords,
                source="amazon-paapi",
                updated_at=now_iso()
            ))
    return out
