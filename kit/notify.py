"""Optional phone alert via the free ntfy app, opening the newest brief when tapped.

Usage: python3 notify.py NTFY_TOPIC PAGE_URL "Short summary line" [ITEM_COUNT]
Only used when the profile sets alerts.ntfy_topic. The topic name is the only key, so it
must be long and random (the intake form generates one).
"""
import sys

import requests


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    topic, page, summary = sys.argv[1], sys.argv[2], sys.argv[3]
    count = sys.argv[4] if len(sys.argv) > 4 else ""
    title = "Your daily digest is ready" + (f" ({count} items)" if count else "")
    r = requests.post(f"https://ntfy.sh/{topic}", data=" ".join(summary.split())[:240].encode("utf-8"),
                      timeout=20, headers={"Title": title, "Click": page, "Tags": "headphones",
                                           "Actions": f"view, Open digest, {page}"})
    r.raise_for_status()
    print("sent", r.json().get("id"))


if __name__ == "__main__":
    main()
