"""Build the spoken script and the email from one digest file, so the transcript in the
email always matches the audio word for word.

digest.json:
  {"date": "YYYY-MM-DD",
   "intro": "Hey Adam, ...",
   "items": [{"text": "One or two spoken sentences.",
              "urls": ["https://article.url", {"url": "https://prompt.url", "label": "Detailed prompt"}],
              "source": "TLDR AI"}, ...],
   "outro": "That's it for this one.",
   "footer": "Window: ... Issues read: ... Buzz: ..."}

Usage:
  python3 build_digest.py script digest.json            -> writes script.txt (for tts.py)
  python3 build_digest.py email digest.json AUDIO_URL   -> writes email.html and email.txt (fallback only)
  python3 build_digest.py site digest.json OUT_DIR [DROPBOX_URL] [EXISTING_INDEX_JSON]
      -> writes OUT_DIR/briefs/<date>.json and OUT_DIR/briefs/index.json (merged with the
         existing index read from the published page), for publishing to the digest page.
         The MP3 is expected at audio/AI-Audio-Digest-<date>.mp3 on the page.

Items may set "wildcard": true; the page tags those.
"""
import os
from datetime import datetime, timezone
import html
import json
import sys


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def spoken(d):
    return [d["intro"], *(i["text"] for i in d["items"]), d["outro"]]


def write_script(d):
    with open("script.txt", "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(p.strip() for p in spoken(d)) + "\n")


def link(u):
    if isinstance(u, dict):
        label = html.escape(u.get("label", ""))
        url = html.escape(u["url"], quote=True)
        return (f"{label}: " if label else "") + f'<a href="{url}">{url}</a>'
    u = html.escape(u, quote=True)
    return f'<a href="{u}">{u}</a>'


def write_email(d, audio):
    esc = html.escape
    h = [f'<p style="font-size:16px"><b><a href="{esc(audio, quote=True)}">&#9654; Listen to the audio (Dropbox)</a></b><br>'
         f'<span style="font-size:12px">{link(audio)}</span></p>',
         '<h3 style="margin-bottom:4px">Transcript</h3>',
         f"<p>{esc(d['intro'])}</p>"]
    t = [f"Listen to the audio (Dropbox): {audio}", "", "TRANSCRIPT", "", d["intro"], ""]
    for item in d["items"]:
        urls = item.get("urls") or []
        src = item.get("source", "")
        src_h = f' <span style="color:#666">({esc(src)})</span>' if src else ""
        src_t = f" ({src})" if src else ""
        h.append(f"<p>{esc(item['text'])}<br>"
                 + "<br>".join(f"&#8594; {link(u)}" for u in urls) + src_h + "</p>")
        flat = [u if isinstance(u, str) else (f"{u['label']}: " if u.get("label") else "") + u["url"] for u in urls]
        t += [item["text"], *(f"-> {u}" for u in flat[:-1]), *(f"-> {u}{src_t}" for u in flat[-1:]), ""]
    h.append(f"<p>{esc(d['outro'])}</p>")
    t += [d["outro"], ""]
    if d.get("footer"):
        h.append(f'<p style="color:#666;font-size:12px">{esc(d["footer"])}</p>')
        t += ["--", d["footer"]]
    with open("email.html", "w", encoding="utf-8") as fh:
        fh.write("\n".join(h) + "\n")
    with open("email.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(t) + "\n")


def write_site(d, out, dropbox="", existing=""):
    date = d["date"]
    brief = {k: d[k] for k in ("date", "intro", "items", "outro", "footer", "headline") if k in d}
    brief["audio"] = {"src": f"audio/AI-Audio-Digest-{date}.mp3"}
    if dropbox:
        brief["audio"]["dropbox"] = dropbox
    if d.get("audio_note"):
        brief["audio"] = {"note": d["audio_note"]}
    index = []
    if existing and os.path.exists(existing):
        with open(existing, encoding="utf-8") as fh:
            index = json.load(fh)
    summary = d.get("headline") or (d["items"][0]["text"] if d["items"] else "")
    index = [e for e in index if e.get("date") != date]
    index.append({"date": date, "items": len(d["items"]), "summary": " ".join(summary.split())[:160],
                  "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "test": bool(d.get("test"))})
    index.sort(key=lambda e: e["date"], reverse=True)
    os.makedirs(os.path.join(out, "briefs"), exist_ok=True)
    with open(os.path.join(out, "briefs", f"{date}.json"), "w", encoding="utf-8") as fh:
        json.dump(brief, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "briefs", "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("script", "email", "site"):
        sys.exit(__doc__)
    digest = load(sys.argv[2])
    if sys.argv[1] == "site":
        if len(sys.argv) < 4:
            sys.exit("site needs OUT_DIR")
        write_site(digest, sys.argv[3], *(sys.argv[4:6]))
    elif sys.argv[1] == "script":
        write_script(digest)
    else:
        if len(sys.argv) < 4:
            sys.exit("email needs AUDIO_URL")
        write_email(digest, sys.argv[3])
