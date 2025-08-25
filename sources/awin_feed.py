from __future__ import annotations
import os, io, zipfile, requests, pandas as pd
from typing import List
from utils.normalize import Item, now_iso, sanitize_text

COMMON_PRICE_HEADERS = ["price","current_price","sale_price","price_eur"]
COMMON_OLDPRICE_HEADERS = ["rrp_price","was_price","previous_price","list_price","old_price"]
COMMON_TITLE_HEADERS = ["product_name","name","title"]
COMMON_URL_HEADERS = ["aw_deeplink","aw_product_url","product_url","merchant_product_url","deeplink","product_link"]
COMMON_IMAGE_HEADERS = ["aw_image_url","merchant_image_url","image_url","image","image_large_url"]

def get_env_header():
    hdr = os.getenv("AWIN_AUTH_HEADER")
    if hdr and ":" in hdr:
        k, v = hdr.split(":", 1)
        return {k.strip(): v.strip()}
    return {}

def fetch_awin_feed(url: str, merchant_slug: str) -> List[Item]:
    if not url:
        return []
    headers = get_env_header()
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.content
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next((n for n in z.namelist() if n.lower().endswith((".csv",".tsv"))), None)
            if not name:
                return []
            data = z.read(name)
    delim = "," if data[:2000].count(b",") >= data[:2000].count(b"\t") else "\t"
    df = pd.read_csv(io.BytesIO(data), sep=delim, dtype=str, keep_default_na=False)

    cols = {c.lower(): c for c in df.columns}
    def first_col(cands):
        for c in cands:
            if c in cols: return cols[c]
        return None

    title_col = first_col([c for c in COMMON_TITLE_HEADERS if c in cols])
    url_col   = first_col([c for c in COMMON_URL_HEADERS if c in cols])
    img_col   = first_col([c for c in COMMON_IMAGE_HEADERS if c in cols])
    price_col = first_col([c for c in COMMON_PRICE_HEADERS if c in cols])
    was_col   = first_col([c for c in COMMON_OLDPRICE_HEADERS if c in cols])

    out: List[Item] = []
    for _, row in df.iterrows():
        title = sanitize_text(row.get(title_col, "")) if title_col else None
        url   = row.get(url_col, "") if url_col else None
        img   = row.get(img_col, "") if img_col else None
        price = row.get(price_col, "") if price_col else None
        was   = row.get(was_col, "") if was_col else None

        try: price_f = float(str(price).replace(",", ".").strip()) if price else None
        except: price_f = None
        try: was_f = float(str(was).replace(",", ".").strip()) if was else None
        except: was_f = None

        if not (title and url):
            continue

        out.append(Item(
            title=title,
            merchant=merchant_slug,
            url=url,
            image=img or None,
            price=price_f,
            old_price=was_f,
            currency="EUR",
            category=None,
            source=f"awin-{merchant_slug}",
            updated_at=now_iso()
        ))
    return out
