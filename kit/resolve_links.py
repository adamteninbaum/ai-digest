"""Resolve newsletter tracking links to clean, direct URLs.

Usage: python3 resolve_links.py URL [URL ...]    (or URLs on stdin, one per line)
Prints a JSON object mapping each original URL to its clean final URL. Any link that
cannot be resolved falls back to the original with tracking params stripped.
"""
import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
TRACKING_PREFIXES = ("utm_", "mc_", "_hs", "hsa_", "pk_", "mtm_", "oly_")
TRACKING_KEYS = {
    "ref", "ref_src", "ref_url", "source", "_bhlid", "jwt_token", "fbclid", "gclid",
    "dclid", "msclkid", "yclid", "igshid", "mkt_tok", "spm", "s_cid", "cmpid",
    "srsltid", "trk", "trkinfo", "sp", "mt", "nlp", "lc", "ep", "_ga", "__s",
    "r", "rd", "vero_id", "vero_conv", "ck_subscriber_id", "sc_cid", "si",
}


def clean(url):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(TRACKING_PREFIXES) and k.lower() not in TRACKING_KEYS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def unwrap_archive(url, session):
    """archive.superhuman.ai/<tweet id> is a mirror page; return the original x.com post."""
    m = re.match(r"https?://archive\.superhuman\.ai/(\d+)", url)
    if not m:
        return None
    try:
        html = session.get(url, timeout=15).text
    except requests.RequestException:
        return None
    hit = re.search(r"https://(?:x|twitter)\.com/\w+/status/" + m.group(1), html)
    return hit.group(0) if hit else None


def resolve(url, session):
    tweet = unwrap_archive(url, session)
    if tweet:
        return tweet
    for method in ("head", "get"):
        try:
            resp = session.request(method, url, allow_redirects=True, timeout=15, stream=True)
            resp.close()
            final = resp.url
            # A HEAD that is refused (405/403) often still redirected; retry with GET if not.
            if final != url or resp.status_code < 400:
                return clean(final)
        except requests.RequestException:
            continue
    return clean(url)


def main():
    urls = sys.argv[1:] or [line.strip() for line in sys.stdin if line.strip()]
    session = requests.Session()
    session.headers["User-Agent"] = UA
    print(json.dumps({u: resolve(u, session) for u in urls}, indent=2))


if __name__ == "__main__":
    main()
