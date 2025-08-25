from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs
from typing import Optional

def ensure_amazon_tag(url: str, tag: Optional[str]) -> str:
    if not tag or "amazon." not in url:
        return url
    u = urlsplit(url)
    q = parse_qs(u.query, keep_blank_values=True)
    if "tag" not in q:
        q["tag"] = [tag]
    new_q = urlencode(q, doseq=True)
    return urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))
