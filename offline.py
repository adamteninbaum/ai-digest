"""Keep recent briefs in a Dropbox folder Adam marks "Available offline" in the Dropbox app.

The digest page cannot work without internet (claude.ai pages cannot install offline
support), so offline listening goes through the Dropbox app: every brief gets a folder in
/Claude/AI Digest Offline/ with its audio and transcript, plus the full audio and text of
any saved articles. Dropbox keeps that folder on the phone. Once a brief has been listened
to (the page records it in its "listened" collection) or is old, it moves to
/Claude/AI Digest Archive/, which is not kept offline, so the phone only holds what is new.

Usage:
  python3 offline.py add BRIEF_JSON BRIEF_MP3 [FULL_DIR]
      Uploads the brief's MP3 and a transcript (with every link) to
      /Claude/AI Digest Offline/<id> <headline>/, plus "Saved - <title> (full audio).mp3" and
      "(text).txt" for each saved article (FULL_DIR, default out/briefs/full; the MP3 from
      audio_full/ where saved.py render leaves it). Safe to run again: files are overwritten.
  python3 offline.py prune LISTENED_JSON [KEEP_DAYS]
      LISTENED_JSON: the page's "listened" collection as JSON (a list of doc ids, or of
      documents with "doc_id"/"id"). Moves to the archive every brief folder that was
      listened to, and every one older than KEEP_DAYS (default 10), but always keeps the
      newest 2. Prints what moved.

Needs DROPBOX_APP_KEY / _SECRET / _REFRESH_TOKEN (files.content.write).
"""
import json
import os
import re
import sys
from datetime import date, timedelta

import requests

from saved import VERIFY, token
from share import make_txt, safe_name, upload

OFFLINE = "/Claude/AI Digest Offline"
ARCHIVE = "/Claude/AI Digest Archive"
ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?\b")


def transcript(brief):
    out = [f"AI Audio Digest {brief.get('id', brief.get('date', ''))}", ""]
    if brief.get("intro"):
        out += [brief["intro"], ""]
    for n, it in enumerate(brief.get("items", []), 1):
        out.append(f"{n:02d}. " + (it.get("title") + "\n" if it.get("title") else "") + it.get("text", ""))
        for u in it.get("urls") or []:
            url, label = (u, "") if isinstance(u, str) else (u.get("url", ""), u.get("label", ""))
            out.append(f"    {label + ': ' if label else ''}{url}")
        if it.get("source"):
            out.append(f"    Source: {it['source']}")
        out.append("")
    if brief.get("outro"):
        out += [brief["outro"], ""]
    if brief.get("footer"):
        out += ["", brief["footer"]]
    return ("\n".join(out) + "\n").encode("utf-8")


def cmd_add(brief_path, mp3, full_dir):
    with open(brief_path, encoding="utf-8") as fh:
        brief = json.load(fh)
    bid = brief.get("id") or brief["date"]
    head = safe_name(brief.get("headline") or "")[:60].rsplit(" ", 1)[0] if brief.get("headline") else ""
    folder = f"{OFFLINE}/{bid}" + (f" {head}" if head else "")
    tok = token()
    with open(mp3, "rb") as fh:
        upload(tok, fh.read(), f"{folder}/01 Brief {bid}.mp3")
    upload(tok, transcript(brief), f"{folder}/02 Transcript {bid}.txt")
    extra = 0
    for it in brief.get("items", []):
        if not (it.get("saved") and it.get("full")):
            continue
        try:
            with open(os.path.join(full_dir, it["saved"] + ".json"), encoding="utf-8") as fh:
                doc = json.load(fh)
        except OSError:
            continue
        name = safe_name(doc.get("title") or it.get("title") or it["saved"])
        upload(tok, make_txt(doc), f"{folder}/Saved - {name} (text).txt")
        src = next((v["src"] for v in doc.get("versions", []) if v.get("src") and not v.get("sample")), "")
        local = os.path.join("audio_full", os.path.basename(src)) if src else ""
        if local and os.path.exists(local):
            with open(local, "rb") as fh:
                upload(tok, fh.read(), f"{folder}/Saved - {name} (full audio).mp3")
        extra += 1
    print(f"offline: {folder} (brief audio, transcript, {extra} saved articles)")


def list_folders(tok, path):
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    r = requests.post("https://api.dropboxapi.com/2/files/list_folder", headers=h, timeout=30, verify=VERIFY,
                      json={"path": path})
    if r.status_code == 409:
        return []
    r.raise_for_status()
    data, out = r.json(), []
    while True:
        out += [e for e in data["entries"] if e[".tag"] == "folder"]
        if not data.get("has_more"):
            return out
        data = requests.post("https://api.dropboxapi.com/2/files/list_folder/continue", headers=h, timeout=30,
                             verify=VERIFY, json={"cursor": data["cursor"]}).json()


def cmd_prune(listened_path, keep_days):
    with open(listened_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    raw = raw.get("documents", raw.get("docs", raw)) if isinstance(raw, dict) else raw
    listened = {(x if isinstance(x, str) else x.get("doc_id") or x.get("id") or "") for x in raw}
    tok = token()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    folders = []
    for f in list_folders(tok, OFFLINE):
        m = ID_RE.match(f["name"])
        if m:
            folders.append((m.group(1), int(m.group(2) or 1), m.group(0), f))
    folders.sort(key=lambda x: (x[0], x[1]), reverse=True)
    cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
    moved = 0
    for i, (day, _, bid, f) in enumerate(folders):
        if i < 2:
            continue  # always keep the newest two on the phone
        why = "listened" if bid in listened else ("older than %d days" % keep_days if day < cutoff else "")
        if not why:
            continue
        r = requests.post("https://api.dropboxapi.com/2/files/move_v2", headers=h, timeout=60, verify=VERIFY,
                          json={"from_path": f["path_display"], "to_path": f"{ARCHIVE}/{f['name']}",
                                "autorename": True})
        if r.ok:
            moved += 1
            print(f"archived {f['name']} ({why})")
        else:
            print(f"could not archive {f['name']}: {r.status_code} {r.text[:150]}")
    print(f"offline folder: {len(folders) - moved} briefs kept, {moved} archived")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "add":
        cmd_add(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else os.path.join("out", "briefs", "full"))
    elif len(sys.argv) >= 3 and sys.argv[1] == "prune":
        cmd_prune(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    else:
        sys.exit(__doc__)
