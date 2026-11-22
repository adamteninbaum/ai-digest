"""Adam's saved Apple News articles: each new one becomes a story in the next brief, with
its full text and full-length audio on the page ("Listen to the full article").

His Mac saves each article to Dropbox /Claude/news-capture/articles/ as a .txt file:
    Title: ...
    Source: ...
    Author: ...      (optional)
    Date: ...        (optional)
    Link: https://apple.news/...
    <blank line>
    body paragraphs...

Usage:
  python3 saved.py fetch USED_JSON [LINKS_JSON]
      Lists the folder with the Dropbox API (DROPBOX_APP_KEY / _SECRET / _REFRESH_TOKEN, the
      same keys dropbox_upload.py uses), skips every article already in USED_JSON (the page's
      saved/used.json; pass "" if it does not exist yet), downloads the rest and writes
      saved/new.json. Prints one line per new article.
      If the Dropbox app may list but not download (no files.content.read scope), it prints
      "NEED_LINKS id:... id:..." and exits 3. Then get temporary links for those ids with the
      Dropbox connector's download_link tool, save its result JSON as LINKS_JSON, and run
      fetch again with it. Nothing is ever used twice: Dropbox file id, content hash and
      article link are all checked against USED_JSON.
  python3 saved.py parse FILE.txt [FILE.txt ...]
      Fallback when the API is not reachable: the Routine saves each article's text (fetched
      with the Dropbox connector) as a local .txt, and this builds saved/new.json from them.
  python3 saved.py render VOICE_ID MODE [USED_JSON]
      Kokoro is slow here, so this stops safely after about 8 minutes (SAVED_BUDGET_S) and
      prints "PARTIAL ..." with exit code 4. Run the SAME command again until it prints the
      files map; finished paragraphs, versions and ElevenLabs audio are never redone.
      MODE is "default" (Adam's brief voice, free), "elevenlabs" or "both". For every article
      in saved/new.json: renders the full article audio, writes out/briefs/full/<key>.json
      (paragraphs + word timings + voice + credits) and audio/full-<key>-<engine>.mp3, and a
      merged out/saved/used.json. Prints the Artifact "files" map as JSON (last stdout line).

A brief item links to its article with "saved": "<key>" (see RUNBOOK step 2c).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

import requests

FOLDER = "/Claude/news-capture/articles"
SAVED_DIR = "saved"
CA = "/root/.ccr/ca-bundle.crt"
VERIFY = CA if os.path.exists(CA) else True
HEADER_KEYS = ("title", "source", "author", "date", "link")


# ---------- Dropbox ----------
def token():
    try:
        key, secret, refresh = (os.environ[k] for k in
                                ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"))
    except KeyError as missing:
        raise RuntimeError(f"missing environment variable {missing}")
    r = requests.post("https://api.dropboxapi.com/oauth2/token", timeout=30, verify=VERIFY,
                      data={"grant_type": "refresh_token", "refresh_token": refresh}, auth=(key, secret))
    r.raise_for_status()
    return r.json()["access_token"]


def list_articles(tok):
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    r = requests.post("https://api.dropboxapi.com/2/files/list_folder", headers=h, timeout=30,
                      verify=VERIFY, data=json.dumps({"path": FOLDER, "recursive": False}))
    r.raise_for_status()
    body = r.json()
    entries = body["entries"]
    while body.get("has_more"):
        r = requests.post("https://api.dropboxapi.com/2/files/list_folder/continue", headers=h, timeout=30,
                          verify=VERIFY, data=json.dumps({"cursor": body["cursor"]}))
        r.raise_for_status()
        body = r.json()
        entries += body["entries"]
    # Only finished .txt files directly in articles/ (not raw/ or other subfolders).
    return sorted((e for e in entries if e[".tag"] == "file" and e["name"].lower().endswith(".txt")),
                  key=lambda e: e.get("client_modified", ""))


def download(tok, file_id):
    r = requests.post("https://content.dropboxapi.com/2/files/download", timeout=60, verify=VERIFY,
                      headers={"Authorization": f"Bearer {tok}",
                               "Dropbox-API-Arg": json.dumps({"path": file_id})})
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace")


# ---------- parsing ----------
def norm_link(u):
    return re.sub(r"[?#].*$", "", (u or "").strip()).rstrip("/").lower()


def parse(text):
    """Header lines up to the first blank line, then the body. Missing fields are ''."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n"))
    head, _, body = text.partition("\n\n")
    meta = {k: "" for k in HEADER_KEYS}
    for line in head.splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip().lower() in meta:
            meta[k.strip().lower()] = v.strip()
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body) if p.strip()]
    # The capture repeats the title as the first body paragraph; drop it (the page shows the title).
    if paras and meta["title"] and paras[0].lower() == meta["title"].lower():
        paras = paras[1:]
    # Photo credit lines such as "(Illustration by ... / Getty Images)" are not worth hearing.
    paras = [p for p in paras if not (p.startswith("(") and p.endswith(")") and len(p) < 300)]
    return meta, paras


def key_for(meta, file_id, content):
    base = file_id or meta.get("link") or content[:200]
    return "s" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]


def article(meta, paras, file_id, content_hash, name, raw):
    words = sum(len(p.split()) for p in paras)
    return {"key": key_for(meta, file_id, raw), "file_id": file_id, "content_hash": content_hash,
            "name": name, **meta, "paragraphs": paras, "words": words,
            "chars": sum(len(p) for p in paras)}


def read_used(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def is_used(used, a):
    for u in used:
        if a["file_id"] and u.get("file_id") == a["file_id"]:
            return True
        if a.get("content_hash") and u.get("content_hash") == a["content_hash"]:
            return True
        if a.get("link") and norm_link(u.get("link")) == norm_link(a["link"]):
            return True
    return False


def write_new(arts):
    os.makedirs(SAVED_DIR, exist_ok=True)
    with open(os.path.join(SAVED_DIR, "new.json"), "w", encoding="utf-8") as fh:
        json.dump(arts, fh, ensure_ascii=False, indent=1)
    for a in arts:
        print(f"new {a['key']}: {a['title']} ({a['source']}) {a['words']} words, "
              f"{a['chars']} chars, ElevenLabs about {a['chars']:,} credits")
    print(f"saved articles new: {len(arts)} (written to {SAVED_DIR}/new.json)")


class NeedLinks(Exception):
    pass


def entry_used(used, e):
    return any(u.get("file_id") == e["id"] or (e.get("content_hash") and u.get("content_hash") == e["content_hash"])
               for u in used)


def cmd_fetch(used_path, links_path=""):
    used = read_used(used_path)
    if links_path:
        # Entries from the Dropbox connector's download_link tool (its "entries" list, saved as JSON).
        with open(links_path, encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("entries", data) if isinstance(data, dict) else data
        entries = [e for e in entries if e.get("name", "").lower().endswith(".txt")]
        tok = None
    else:
        tok = token()
        entries = list_articles(tok)
    new = [e for e in entries if not entry_used(used, e)]
    arts, seen = [], set()
    for e in new:
        if links_path:
            r = requests.get(e["download_url"], timeout=60, verify=VERIFY)
            r.raise_for_status()
            raw = r.content.decode("utf-8", errors="replace")
        else:
            try:
                raw = download(tok, e["id"])
            except requests.HTTPError as err:
                if "files.content.read" in (err.response.text if err.response is not None else ""):
                    # The Dropbox app can list but not download. The Routine gets temporary links
                    # from the Dropbox connector instead (RUNBOOK step 2c).
                    print("NEED_LINKS " + " ".join(x["id"] for x in new))
                    sys.exit(3)
                raise
        meta, paras = parse(raw)
        if not paras:
            print(f"skip {e['name']}: no body text", file=sys.stderr)
            continue
        a = article(meta, paras, e["id"], e.get("content_hash", ""), e["name"], raw)
        if is_used(used, a) or norm_link(a["link"]) in seen:
            continue
        seen.add(norm_link(a["link"]))
        arts.append(a)
    write_new(arts)


def cmd_parse(paths, used_path=""):
    used = read_used(used_path)
    arts = []
    for p in paths:
        raw = open(p, encoding="utf-8").read()
        meta, paras = parse(raw)
        if paras:
            a = article(meta, paras, "", hashlib.sha256(raw.encode()).hexdigest(), os.path.basename(p), raw)
            if not is_used(used, a):
                arts.append(a)
    write_new(arts)


# ---------- audio ----------
def spoken_paragraphs(a):
    """What is read aloud, paragraph by paragraph. The first is a short spoken title line."""
    by = f", by {a['author']}" if a.get("author") else ""
    title = a["title"].rstrip()
    title = title if title[-1:] in ".!?" else title + "."
    first = f"{title} From {a['source']}{by}." if a.get("source") else title
    return [first] + a["paragraphs"]


def ffprobe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


START = time.time()
BUDGET = float(os.environ.get("SAVED_BUDGET_S", "480"))  # stop safely before a 10 minute Bash limit


class Partial(Exception):
    pass


def kokoro_resumable(paras, out_mp3, voice):
    """Kokoro, one paragraph at a time, each saved to disk. If the time budget runs out it
    raises Partial; running again continues from the first missing paragraph."""
    import numpy as np
    import soundfile as sf
    import tts
    cache = os.path.splitext(out_mp3)[0] + f".{voice}.parts"
    os.makedirs(cache, exist_ok=True)
    k = None
    for i, para in enumerate(paras):
        wav = os.path.join(cache, f"{i:04d}.wav")
        if os.path.exists(wav):
            continue
        if time.time() - START > BUDGET:
            raise Partial(f"{i} of {len(paras)} paragraphs done")
        if k is None:
            from kokoro_onnx import Kokoro
            k = Kokoro(*tts.kokoro_model())
        samples, sr = k.create(para, voice=voice, speed=1.05, lang="en-gb" if voice.startswith("b") else "en-us")
        sf.write(wav + ".tmp.wav", samples, sr)
        os.replace(wav + ".tmp.wav", wav)
    # Same timing estimate as tts.kokoro: spread each paragraph's duration by word length.
    gap_s, t, chunks, words, sr = 0.35, 0.0, [], [], 24000
    for i, para in enumerate(paras):
        samples, sr = sf.read(os.path.join(cache, f"{i:04d}.wav"), dtype="float32")
        dur = len(samples) / sr
        toks = para.split()
        weights = [len(w) + 1 for w in toks]
        total = sum(weights) or 1
        pos = t
        for w, wt in zip(toks, weights):
            span = dur * wt / total
            words.append({"text": w, "start": round(pos * 1000), "end": round((pos + span) * 1000)})
            pos += span
        chunks += [samples, np.zeros(int(sr * gap_s), dtype=samples.dtype)]
        t += dur + gap_s
    wav = os.path.splitext(out_mp3)[0] + ".wav"
    sf.write(wav, np.concatenate(chunks), sr)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-codec:a", "libmp3lame",
                    "-b:a", "64k", out_mp3], check=True)
    os.remove(wav)
    return words


def render_default(a, voice, out_mp3):
    """Adam's brief voice, free: Edge for "edge_andrew" (Kokoro am_michael if Microsoft refuses,
    like tts.py), otherwise the Kokoro voice he picked."""
    import tts
    paras = spoken_paragraphs(a)
    voice = (voice or "edge_andrew").strip()
    edge_voice = tts.EDGE_VOICE if voice.startswith("edge_") else voice if voice.endswith("Neural") else None
    if edge_voice and os.environ.get("TTS_ENGINE", "").lower() != "kokoro":
        try:
            tts.edge("\n\n".join(paras), out_mp3, edge_voice)
            with open(tts.words_path(out_mp3), encoding="utf-8") as fh:
                return {"engine": "edge", "voice": "edge_andrew", "credits": 0, "words": json.load(fh)}
        except Exception as e:  # noqa: BLE001
            print(f"{e}; falling back to Kokoro", file=sys.stderr)
    kv = tts.KOKORO_VOICE if edge_voice else voice
    return {"engine": "kokoro", "voice": kv, "credits": 0, "words": kokoro_resumable(paras, out_mp3, kv)}


def render_eleven(a, out_mp3):
    import elevenlabs_tts
    return elevenlabs_tts.render(spoken_paragraphs(a), out_mp3)


def cmd_render(voice, mode, used_path=""):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_digest import align
    with open(os.path.join(SAVED_DIR, "new.json"), encoding="utf-8") as fh:
        arts = json.load(fh)
    mode = (mode or "default").lower()
    files = {}
    os.makedirs("out/briefs/full", exist_ok=True)
    os.makedirs("out/saved", exist_ok=True)
    os.makedirs("audio_full", exist_ok=True)
    for a in arts:
        paras = spoken_paragraphs(a)
        doc = {"key": a["key"], **{k: a.get(k, "") for k in HEADER_KEYS}, "paragraphs": paras,
               "words": a["words"], "chars": a["chars"], "versions": []}
        jobs = []
        if mode in ("default", "both"):
            jobs.append(("default", lambda out, a=a: render_default(a, voice, out)))
        if mode in ("elevenlabs", "both"):
            jobs.append(("elevenlabs", lambda out, a=a: render_eleven(a, out)))
        for kind, fn in jobs:
            name = f"full-{a['key']}-{'eleven' if kind == 'elevenlabs' else 'default'}.mp3"
            local = os.path.join("audio_full", name)
            meta = local + ".meta.json"
            try:
                if os.path.exists(meta) and os.path.exists(local):
                    with open(meta, encoding="utf-8") as fh:
                        r = json.load(fh)  # finished on an earlier call
                else:
                    r = fn(local)
                    with open(meta, "w", encoding="utf-8") as fh:
                        json.dump(r, fh, ensure_ascii=False)
            except Partial as p:
                print(f"PARTIAL {a['key']} {kind}: {p}. Run the same command again to continue.")
                sys.exit(4)
            except Exception as e:  # noqa: BLE001
                print(f"{a['key']} {kind} audio failed: {str(e)[:300]}", file=sys.stderr)
                doc["versions"].append({"kind": kind, "note": f"Audio failed: {str(e)[:160]}"})
                if kind == "elevenlabs" and mode == "elevenlabs":
                    # "ElevenLabs instead" failed: fall back to the free brief voice so the article still plays.
                    try:
                        r = render_default(a, voice, local.replace("-eleven", "-default"))
                        kind, name, local = "default", name.replace("-eleven", "-default"), local.replace("-eleven", "-default")
                    except Partial as p:
                        print(f"PARTIAL {a['key']} fallback: {p}. Run the same command again to continue.")
                        sys.exit(4)
                    except Exception as e2:  # noqa: BLE001
                        print(f"{a['key']} fallback audio failed: {e2}", file=sys.stderr)
                        continue
                else:
                    continue
            v = {"kind": kind, "engine": r["engine"], "voice": r["voice"], "credits": r["credits"],
                 "credits_estimated": r.get("credits_estimated", False),
                 "src": "audio/" + name, "seconds": round(ffprobe_seconds(local)),
                 "timing": align(paras, r["words"])}
            if r.get("voice_name"):
                v["voice_name"] = r["voice_name"]
            if r.get("model"):
                v["model"] = r["model"]
            doc["versions"].append(v)
            files["audio/" + name] = local
            print(f"{a['key']} {kind}: {r['engine']} {r['voice']} {v['seconds']}s credits={r['credits']}")
        path = f"out/briefs/full/{a['key']}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        files[f"briefs/full/{a['key']}.json"] = path
    used = read_used(used_path)
    for a in arts:
        used.append({"key": a["key"], "file_id": a["file_id"], "content_hash": a["content_hash"],
                     "link": a["link"], "title": a["title"], "name": a["name"]})
    with open("out/saved/used.json", "w", encoding="utf-8") as fh:
        json.dump(used, fh, ensure_ascii=False, indent=1)
    files["saved/used.json"] = "out/saved/used.json"
    print(json.dumps(files))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "parse", "render"):
        sys.exit(__doc__)
    if sys.argv[1] == "fetch":
        cmd_fetch(sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else "")
    elif sys.argv[1] == "parse":
        cmd_parse(sys.argv[2:])
    else:
        if len(sys.argv) < 4:
            sys.exit("render needs VOICE_ID MODE [USED_JSON]")
        cmd_render(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
