"""Build the spoken script and the email from one digest file, so the transcript in the
email always matches the audio word for word.

digest.json:
  {"date": "YYYY-MM-DD",
   "intro": "Hey Adam, ...",
   "items": [{"text": "One or two spoken sentences.", "urls": ["https://clean.url"],
              "source": "TLDR AI"}, ...],
   "outro": "That's it for this one.",
   "footer": "Window: ... Issues read: ... Buzz: ..."}

Usage:
  python3 build_digest.py script digest.json            -> writes script.txt (for tts.py)
  python3 build_digest.py email digest.json AUDIO_URL   -> writes email.html and email.txt
"""
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
        t += [item["text"], *(f"-> {u}" for u in urls[:-1]), *(f"-> {u}{src_t}" for u in urls[-1:]), ""]
    h.append(f"<p>{esc(d['outro'])}</p>")
    t += [d["outro"], ""]
    if d.get("footer"):
        h.append(f'<p style="color:#666;font-size:12px">{esc(d["footer"])}</p>')
        t += ["--", d["footer"]]
    with open("email.html", "w", encoding="utf-8") as fh:
        fh.write("\n".join(h) + "\n")
    with open("email.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(t) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("script", "email"):
        sys.exit(__doc__)
    digest = load(sys.argv[2])
    if sys.argv[1] == "script":
        write_script(digest)
    else:
        if len(sys.argv) < 4:
            sys.exit("email needs AUDIO_URL")
        write_email(digest, sys.argv[3])
