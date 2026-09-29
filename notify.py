"""Push a phone alert (via ntfy) that opens the newest brief when tapped.

Usage: python3 notify.py BRIEF_ID "Short summary line" [ITEM_COUNT]

Adam gets these through the free ntfy app, subscribed to the topic below. The topic name
is the only key, so keep it unguessable; set NTFY_TOPIC to override it.
"""
import os
import sys

import requests

TOPIC = os.environ.get("NTFY_TOPIC", "ai-digest-adam-5f3fv2j1pzpx9dr7")
PAGE = "https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    brief_id, summary = sys.argv[1], sys.argv[2]
    count = sys.argv[3] if len(sys.argv) > 3 else ""
    link = f"{PAGE}#d{brief_id}"
    title = "Your AI digest is ready" + (f" ({count} items)" if count else "")
    body = " ".join(summary.split())[:240]
    r = requests.post(f"https://ntfy.sh/{TOPIC}", data=body.encode("utf-8"), timeout=20, headers={
        "Title": title,
        "Click": link,
        "Tags": "headphones",
        "Actions": f"view, Open digest, {link}",
    })
    r.raise_for_status()
    print("sent", r.json().get("id"), link)


if __name__ == "__main__":
    main()
