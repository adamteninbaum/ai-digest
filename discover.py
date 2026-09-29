"""Find what AI stories are hot online right now, beyond Adam's newsletters.

Usage: python3 discover.py [HOURS]   (default 24) -> prints candidates as JSON

Sources (all free, no keys):
  - Hacker News: AI/LLM stories with 100+ points in the window (points, comments)
  - Techmeme: the day's top tech headlines (RSS)
  - Google News: top "artificial intelligence" stories of the last day (RSS)
  - smol.ai AI News: the latest daily AI roundup issue (RSS)
  - Hugging Face: today's most upvoted papers
Reddit and GitHub Trending block unauthenticated requests, so they are not used.
Any source that fails is skipped and listed under "errors".
"""
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

UA = {"User-Agent": "Mozilla/5.0 (ai-digest; personal newsletter summarizer)"}
AI_WORDS = re.compile(r"\b(ai|a\.i\.|llm|llms|gpt|openai|anthropic|claude|gemini|deepmind|mistral|llama|"
                      r"agent|agents|agentic|model|models|neural|diffusion|sora|veo|midjourney|runway|"
                      r"nvidia|machine learning|chatbot|copilot|genai|generative|robot|robotics)\b", re.I)


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=20, **kw)
    r.raise_for_status()
    return r


def hacker_news(hours):
    since = int(time.time()) - hours * 3600
    seen, out = set(), []
    for q in ("AI", "LLM", "OpenAI", "Anthropic", "agents", "model"):
        url = ("https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=30&query=" + quote(q)
               + "&numericFilters=" + quote(f"points>80,created_at_i>{since}"))
        for h in get(url).json()["hits"]:
            if h["objectID"] in seen:
                continue
            seen.add(h["objectID"])
            out.append({"source": "Hacker News", "title": h["title"],
                        "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "points": h["points"], "comments": h.get("num_comments", 0)})
    out.sort(key=lambda x: x["points"], reverse=True)
    return out[:20]


def rss(url, source, limit, ai_only=True):
    root = ET.fromstring(get(url).content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        if ai_only and not AI_WORDS.search(title + " " + desc[:300]):
            continue
        out.append({"source": source, "title": title, "url": link,
                    "published": (item.findtext("pubDate") or "").strip(),
                    "summary": " ".join(desc.split())[:280]})
        if len(out) >= limit:
            break
    return out


def smol_ai():
    from email.utils import parsedate_to_datetime
    items = rss("https://news.smol.ai/rss.xml", "smol.ai AI News", 1000, ai_only=False)

    def when(i):
        try:
            return parsedate_to_datetime(i["published"]).timestamp()
        except Exception:
            return 0
    items = sorted(items, key=when, reverse=True)[:1]
    if items and when(items[0]) < time.time() - 3 * 86400:
        return []  # the feed has gone quiet; a stale issue is not news
    for i in items:
        i["note"] = "Daily AI roundup; open it for the day's top Twitter/Reddit/Discord AI discussion."
    return items


def hf_papers():
    papers = get("https://huggingface.co/api/daily_papers?limit=30").json()
    out = []
    for p in papers:
        paper = p.get("paper", {})
        out.append({"source": "Hugging Face papers", "title": p.get("title") or paper.get("title", ""),
                    "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                    "upvotes": paper.get("upvotes", 0),
                    "summary": " ".join((paper.get("summary") or "").split())[:280]})
    out.sort(key=lambda x: x["upvotes"], reverse=True)
    return out[:8]


def main():
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    result, errors = {}, {}
    jobs = {
        "hacker_news": lambda: hacker_news(hours),
        "techmeme": lambda: rss("https://www.techmeme.com/feed.xml", "Techmeme", 15),
        "google_news": lambda: rss("https://news.google.com/rss/search?q=artificial+intelligence+when:1d"
                                   "&hl=en-US&gl=US&ceid=US:en", "Google News", 20, ai_only=False),
        "smol_ai": smol_ai,
        "hf_papers": hf_papers,
    }
    for name, job in jobs.items():
        try:
            result[name] = job()
        except Exception as e:  # one dead source must not sink the run
            errors[name] = f"{type(e).__name__}: {e}"[:200]
    result["errors"] = errors
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
