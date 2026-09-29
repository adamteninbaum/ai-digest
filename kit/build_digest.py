"""Build the spoken script and the email from one digest file, so the transcript in the
email always matches the audio word for word.

digest.json:
  {"date": "YYYY-MM-DD",
   "intro": "Hey Sam, ...",
   "items": [{"text": "One or two spoken sentences.",
              "urls": ["https://article.url", {"url": "https://prompt.url", "label": "Detailed prompt"}],
              "source": "TLDR AI"}, ...],
   "outro": "That's it for this one.",
   "footer": "Window: ... Issues read: ... Buzz: ..."}

Usage:
  python3 build_digest.py script digest.json            -> writes script.txt (for tts.py)
  python3 build_digest.py email digest.json AUDIO_URL   -> writes email.html and email.txt (fallback only)
  python3 build_digest.py nextid EXISTING_INDEX_JSON DATE
      -> prints the id for a new brief: DATE, or DATE-2, DATE-3... if that day already has
         briefs. Put it in digest.json as "id" and use it in the MP3 file name.
  python3 build_digest.py site digest.json OUT_DIR [DROPBOX_URL] [EXISTING_INDEX_JSON] [WORDS_JSON]
      -> writes OUT_DIR/briefs/<date>.json and OUT_DIR/briefs/index.json (merged with the
         existing index read from the published page), for publishing to the digest page.
         The MP3 is expected at audio/AI-Audio-Digest-<id>.mp3 on the page. Existing briefs
         are never replaced; a second brief on the same day gets its own id. WORDS_JSON is the
         .words.json tts.py wrote; with it the page highlights each word as it is spoken.

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


def read_index(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def next_id(index, date):
    taken = {e.get("id") or e["date"] for e in index}
    if date not in taken:
        return date
    n = 2
    while f"{date}-{n}" in taken:
        n += 1
    return f"{date}-{n}"


def _norm(t):
    return "".join(ch for ch in t.lower() if ch.isalnum())


def align(paragraphs, words):
    """Map TTS word timings onto transcript tokens.

    Tokens are each paragraph split on whitespace, the same split the page does in JS
    (text.trim().split(/\s+/)). Returns [[paragraph, token, start_ms, end_ms], ...].
    """
    tokens = [(p, t, _norm(tok)) for p, text in enumerate(paragraphs)
              for t, tok in enumerate(text.split())]
    out, i = [], 0
    for w in words:
        wn = _norm(w["text"])
        if not wn:
            continue
        window = range(i, min(i + 8, len(tokens)))
        hit = next((j for j in window if tokens[j][2] == wn), None)
        if hit is None:
            hit = next((j for j in window if tokens[j][2] and (wn in tokens[j][2] or tokens[j][2] in wn)), None)
        if hit is None:
            continue
        p, t, _ = tokens[hit]
        if out and out[-1][0] == p and out[-1][1] == t:
            out[-1][3] = w["end"]  # several spoken words inside one token ("5.5", "$1B")
        else:
            out.append([p, t, w["start"], w["end"]])
        # stay on a token until its last spoken part ("twelve" "million" "view")
        i = hit + 1 if tokens[hit][2].endswith(wn) or wn.endswith(tokens[hit][2]) else hit
    return out


def write_site(d, out, dropbox="", existing="", words_path=""):
    date = d["date"]
    index = read_index(existing)
    bid = d.get("id") or next_id(index, date)
    brief = {k: d[k] for k in ("date", "intro", "items", "outro", "footer", "headline") if k in d}
    brief["id"] = bid
    brief["audio"] = {"src": f"audio/AI-Audio-Digest-{bid}.mp3"}
    if dropbox:
        brief["audio"]["dropbox"] = dropbox
    if d.get("audio_note"):
        brief["audio"] = {"note": d["audio_note"]}
    elif words_path and os.path.exists(words_path):
        with open(words_path, encoding="utf-8") as fh:
            words = json.load(fh)
        paragraphs = [d.get("intro", "")] + [i["text"] for i in d["items"]] + [d.get("outro", "")]
        brief["timing"] = align(paragraphs, words)
    summary = d.get("headline") or (d["items"][0]["text"] if d["items"] else "")
    index = [e for e in index if (e.get("id") or e["date"]) != bid]
    index.append({"id": bid, "date": date, "items": len(d["items"]), "summary": " ".join(summary.split())[:160],
                  "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "test": bool(d.get("test"))})
    index.sort(key=lambda e: (e["date"], e.get("published_at", "")), reverse=True)
    os.makedirs(os.path.join(out, "briefs"), exist_ok=True)
    with open(os.path.join(out, "briefs", f"{bid}.json"), "w", encoding="utf-8") as fh:
        json.dump(brief, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "briefs", "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    print(bid)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("script", "email", "site", "nextid"):
        sys.exit(__doc__)
    if sys.argv[1] == "nextid":
        if len(sys.argv) < 4:
            sys.exit("nextid needs EXISTING_INDEX_JSON DATE")
        print(next_id(read_index(sys.argv[2]), sys.argv[3]))
        sys.exit(0)
    digest = load(sys.argv[2])
    if sys.argv[1] == "site":
        if len(sys.argv) < 4:
            sys.exit("site needs OUT_DIR")
        write_site(digest, sys.argv[3], *(sys.argv[4:7]))
    elif sys.argv[1] == "script":
        write_script(digest)
    else:
        if len(sys.argv) < 4:
            sys.exit("email needs AUDIO_URL")
        write_email(digest, sys.argv[3])
