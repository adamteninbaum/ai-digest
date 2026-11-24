"""Push a phone alert (via ntfy) that opens the newest brief when tapped.

Usage: python3 notify.py [--not-before HH:MM] BRIEF_ID "Short summary line" [ITEM_COUNT]

--not-before 08:00 holds the alert until that time today, US Eastern: ntfy keeps the message
and delivers it then (its "At" header). Already past that time: it is sent right away.

Adam gets these through the free ntfy app, subscribed to the topic below. The topic name
is the only key, so keep it unguessable; set NTFY_TOPIC to override it.
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TOPIC = os.environ.get("NTFY_TOPIC", "ai-digest-adam-5f3fv2j1pzpx9dr7")
PAGE = "https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy"


def hold_until(hhmm):
    """Unix time of HH:MM today in US Eastern, or None if that time has already passed."""
    now = datetime.now(ZoneInfo("America/New_York"))
    h, m = (int(x) for x in hhmm.split(":"))
    at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return int(at.timestamp()) if at - now > timedelta(seconds=15) else None


def main():
    args = sys.argv[1:]
    at = None
    if args[:1] == ["--not-before"]:
        at = hold_until(args[1])
        args = args[2:]
    if len(args) < 2:
        sys.exit(__doc__)
    brief_id, summary = args[0], args[1]
    count = args[2] if len(args) > 2 else ""
    link = f"{PAGE}#d{brief_id}"
    title = "Your AI digest is ready" + (f" ({count} items)" if count else "")
    body = " ".join(summary.split())[:240]
    r = requests.post(f"https://ntfy.sh/{TOPIC}", data=body.encode("utf-8"), timeout=20, headers={
        "Title": title,
        "Click": link,
        "Tags": "headphones",
        "Actions": f"view, Open digest, {link}",
        **({"At": str(at)} if at else {}),
    })
    r.raise_for_status()
    when = (" (delivers " + datetime.fromtimestamp(at, ZoneInfo("America/New_York")).strftime("%-I:%M %p ET") + ")") if at else ""
    print("sent", r.json().get("id"), link + when)


if __name__ == "__main__":
    main()
