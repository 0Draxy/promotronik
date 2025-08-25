from __future__ import annotations
import os
from typing import List, Optional
from .utils import paapi_client
from utils.normalize import Item, now_iso, sanitize_text

def fetch_amazon_items(marketplace: str, partner_tag: Optional[str], queries: List[dict]) -> List[Item]:
    access = os.getenv("AMAZON_ACCESS_KEY")
    secret = os.getenv("AMAZON_SECRET_KEY")
    ptag   = partner_tag or os.getenv("AMAZON_PARTNER_TAG")
    if not (access and secret and ptag):
        print("[amazon] missing keys or partner tag → skipping")
        return []

    api = paapi_client(access, secret, marketplace, ptag)
    items: List[Item] = []

    for q in queries:
        keywords = q.get("keywords")
        browse_node = q.get("browse_node")
        sort_by = q.get("sort_by") or "SalesRank"
        min_savings = float(q.get("min_savings_percent") or 0)

        page = 1
        max_pages = 1
        while page <= max_pages:
            data = api.search_items(
                keywords=keywords,
                browse_node=browse_node,
                sort_by=sort_by,
                page=page
            )
            if not data or not data.get("ItemsResult") or not data["ItemsResult"].get("Items"):
                break
            for it in data["ItemsResult"]["Items"]:
                title = sanitize_text(it.get("ItemInfo", {}).get("Title", {}).get("DisplayValue"))
                url = it.get("DetailPageURL")
                img = (it.get("Images", {}) or {}).get("Primary", {}).get("Medium", {}).get("URL")
                offers = it.get("Offers", {})

                price = None
                old_price = None
                currency = None

                lpo = (offers.get("Listings") or [{}])[0].get("Price") if offers.get("Listings") else None
                if lpo:
                    amount = lpo.get("Amount")
                    currency = lpo.get("Currency")
                    price = float(amount) if amount is not None else None

                s_o = (offers.get("Summaries") or [{}])[0] if offers.get("Summaries") else {}
                savings = (s_o.get("Savings") or {}).get("Amount")
                basis = (s_o.get("Price", {}) or {}).get("Amount")
                if savings and basis:
                    old_price = float(basis)
                    price = float(basis) - float(savings)

                if min_savings and old_price and price:
                    pct = (old_price - price) / old_price * 100.0
                    if pct < min_savings:
                        continue

                if not (title and url):
                    continue

                items.append(Item(
                    title=title,
                    merchant="amazon",
                    url=url,
                    image=img,
                    price=price,
                    old_price=old_price,
                    currency=currency or "EUR",
                    category=keywords,
                    source="amazon-paapi",
                    updated_at=now_iso()
                ))
            page += 1

    return items
