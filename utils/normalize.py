from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hashlib, re

@dataclass
class Item:
    title: str
    merchant: str
    url: str
    image: Optional[str]
    price: Optional[float]
    old_price: Optional[float]
    currency: Optional[str]
    category: Optional[str]
    source: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = hashlib.md5((self.merchant.lower() + "|" + (self.title or "") + "|" + (self.url or "")).encode("utf-8")).hexdigest()
        if self.price and self.old_price and self.old_price > self.price:
            d["discount_percent"] = round((self.old_price - self.price) / self.old_price * 100, 1)
        else:
            d["discount_percent"] = None
        return d

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sanitize_text(s: Optional[str]) -> Optional[str]:
    if not s: return s
    return re.sub(r"\s+", " ", s).strip()

def dedupe(items: list[Item]) -> list[Item]:
    seen = set()
    uniq = []
    for it in items:
        key = (it.merchant.lower(), (it.title or "")[:120].lower())
        if key in seen: 
            continue
        seen.add(key)
        uniq.append(it)
    return uniq
