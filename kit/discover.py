"""Find today's most talked-about stories online for a person's topics.

Usage: python3 discover.py --topics "AI, NBA, Cooking" [--hours 24] [--local "Chicago"]
Prints candidates as JSON, grouped by source. Every source is free and needs no key.

  - Google News: top stories for each topic (and the local area, if given)
  - Hacker News: stories with 80+ points, when a topic is tech-related
  - Techmeme: top tech headlines, when a topic is tech-related
  - Hugging Face: most upvoted AI papers, when a topic is AI-related
Reddit and GitHub Trending block unauthenticated requests, so they are not used.
A source that fails is listed under "errors" and the rest still return.
Google News links are Google wrappers: look up the publisher's own URL before using one.
"""
import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

UA = {"User-Agent": "Mozilla/5.0 (daily-digest-kit; personal news summarizer)"}
TECH = re.compile(r"\b(ai|a\.i\.|tech|technology|software|coding|programming|startup|startups|gadget|"
                  r"gadgets|crypto|robot|robotics|machine learning|llm|design|gaming|games|science|"
                  r"space|security|cyber)\b", re.I)
AI = re.compile(r"\b(ai|a\.i\.|artificial intelligence|machine learning|llm|llms|generative)\b", re.I)


def get(url):
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r


def rss_items(url, source, limit):
    root = ET.fromstring(get(url).content)
    out = []
    for item in root.iter("item"):
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        out.append({"source": source, "title": (item.findtext("title") or "").strip(),
                    "url": (item.findtext("link") or "").strip(),
                    "published": (item.findtext("pubDate") or "").strip(),
                    "summary": " ".join(desc.split())[:240]})
        if len(out) >= limit:
            break
    return out


def google_news(query, limit=8):
    url = ("https://news.google.com/rss/search?q=" + quote(f"{query} when:1d")
           + "&hl=en-US&gl=US&ceid=US:en")
    items = rss_items(url, "Google News", limit)
    for i in items:
        i["topic"] = query
    return items


def hacker_news(hours):
    since = int(time.time()) - hours * 3600
    url = ("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=40&numericFilters="
           + quote(f"created_at_i>{since}"))
    hits = get(url).json()["hits"]
    out = [{"source": "Hacker News", "title": h["title"],
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
            "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}",
            "points": h.get("points", 0), "comments": h.get("num_comments", 0)} for h in hits]
    out = [o for o in out if o["points"] >= 80]
    out.sort(key=lambda x: x["points"], reverse=True)
    return out[:20]


def hf_papers():
    papers = get("https://huggingface.co/api/daily_papers?limit=30").json()
    out = [{"source": "Hugging Face papers", "title": p.get("title") or p.get("paper", {}).get("title", ""),
            "url": f"https://huggingface.co/papers/{p.get('paper', {}).get('id', '')}",
            "upvotes": p.get("paper", {}).get("upvotes", 0)} for p in papers]
    out.sort(key=lambda x: x["upvotes"], reverse=True)
    return out[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", required=True, help="comma-separated topics")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--local", default="", help="city or region for local news")
    args = ap.parse_args()
    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    joined = " ".join(topics)
    result, errors = {"google_news": []}, {}
    for t in topics + ([f"{args.local} local news"] if args.local else []):
        try:
            result["google_news"] += google_news(t)
        except Exception as e:
            errors[f"google_news:{t}"] = f"{type(e).__name__}: {e}"[:200]
    if TECH.search(joined):
        for name, job in (("hacker_news", lambda: hacker_news(args.hours)),
                          ("techmeme", lambda: rss_items("https://www.techmeme.com/feed.xml", "Techmeme", 15))):
            try:
                result[name] = job()
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"[:200]
    if AI.search(joined):
        try:
            result["hf_papers"] = hf_papers()
        except Exception as e:
            errors["hf_papers"] = f"{type(e).__name__}: {e}"[:200]
    result["errors"] = errors
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
