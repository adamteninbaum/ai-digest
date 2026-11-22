"""ElevenLabs renderer for full saved articles (the "voice test" option), with word timings.

Usage: python3 elevenlabs_tts.py SCRIPT.txt OUT.mp3     (paragraphs separated by blank lines)
Or from saved.py: render(paragraphs, out_mp3).

The API key is NEVER stored in this repo or typed into chat. It is a network secret on the
cloud environment for host api.elevenlabs.io, header "xi-api-key": the session proxy adds
the real key to every request to that host. This script sends a placeholder that the proxy
replaces. ELEVENLABS_API_KEY, if set, is used instead (for running on a Mac).

Settings (optional, non-secret environment variables):
  ELEVENLABS_VOICE_ID  voice to use (default JBFqnCBsd6RMkjVDRZzb, "George", a premade voice
                       every account has)
  ELEVENLABS_MODEL     default eleven_multilingual_v2 (about 1 credit per character);
                       eleven_flash_v2_5 / eleven_turbo_v2_5 cost about 0.5 credit per character.

Long text is sent in chunks of about 4,000 characters on paragraph breaks (with previous/next
text for smooth joins) and joined with ffmpeg. Credits are read from the "character-cost"
response header when ElevenLabs sends it, else estimated from the character count.
"""
import base64
import json
import os
import subprocess
import sys

import requests

API = "https://api.elevenlabs.io/v1"
CA = "/root/.ccr/ca-bundle.crt"
VERIFY = CA if os.path.exists(CA) else True
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
RATE = {"eleven_flash_v2_5": 0.5, "eleven_turbo_v2_5": 0.5, "eleven_flash_v2": 0.5, "eleven_turbo_v2": 0.5}
CHUNK = 4000


def headers():
    # Placeholder: the cloud proxy swaps in the real key stored as a network secret.
    return {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "proxy-injects-this"),
            "Content-Type": "application/json"}


def chunks(paragraphs):
    out, cur = [], []
    for p in paragraphs:
        if cur and sum(len(x) + 2 for x in cur) + len(p) > CHUNK:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def char_words(alignment, offset_s):
    """Group per-character timings into words: [{"text", "start", "end"}] in ms."""
    chars = alignment["characters"]
    st = alignment["character_start_times_seconds"]
    en = alignment["character_end_times_seconds"]
    words, buf, s0, e0 = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if buf:
                words.append({"text": buf, "start": round((s0 + offset_s) * 1000), "end": round((e0 + offset_s) * 1000)})
            buf, s0 = "", None
            continue
        if s0 is None:
            s0 = s
        buf += c
        e0 = e
    if buf:
        words.append({"text": buf, "start": round((s0 + offset_s) * 1000), "end": round((e0 + offset_s) * 1000)})
    return words


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def voice_name():
    try:
        r = requests.get(f"{API}/voices/{VOICE}", headers=headers(), timeout=20, verify=VERIFY)
        return r.json().get("name", "") if r.ok else ""
    except Exception:  # noqa: BLE001
        return ""


def render(paragraphs, out_mp3):
    parts = chunks(paragraphs)
    tmp, words, offset, credits, header_seen = [], [], 0.0, 0.0, True
    for i, part in enumerate(parts):
        text = "\n\n".join(part)
        body = {"text": text, "model_id": MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
        if i > 0:
            body["previous_text"] = "\n\n".join(parts[i - 1])[-1000:]
        if i < len(parts) - 1:
            body["next_text"] = "\n\n".join(parts[i + 1])[:1000]
        r = requests.post(f"{API}/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_64",
                          headers=headers(), data=json.dumps(body), timeout=300, verify=VERIFY)
        if r.status_code in (401, 403):
            raise RuntimeError(f"ElevenLabs refused the key ({r.status_code}). Is the api.elevenlabs.io "
                               f"network secret saved on the cloud environment? {r.text[:200]}")
        if not r.ok:
            raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
        cost = r.headers.get("character-cost") or r.headers.get("x-character-count")
        if cost:
            credits += float(cost)
        else:
            header_seen = False
            credits += len(text) * RATE.get(MODEL, 1.0)
        data = r.json()
        path = f"{os.path.splitext(out_mp3)[0]}.part{i}.mp3"
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(data["audio_base64"]))
        tmp.append(path)
        al = data.get("alignment") or data.get("normalized_alignment")
        if al:
            words += char_words(al, offset)
        offset += duration(path)
    if len(tmp) == 1:
        os.replace(tmp[0], out_mp3)
    else:
        lst = os.path.splitext(out_mp3)[0] + ".parts.txt"
        with open(lst, "w") as fh:
            fh.writelines(f"file '{os.path.abspath(p)}'\n" for p in tmp)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", out_mp3], check=True)
        for p in tmp + [lst]:
            os.remove(p)
    with open(os.path.splitext(out_mp3)[0] + ".words.json", "w", encoding="utf-8") as fh:
        json.dump(words, fh, ensure_ascii=False)
    return {"engine": "elevenlabs", "voice": VOICE, "voice_name": voice_name(), "model": MODEL,
            "credits": round(credits), "credits_estimated": not header_seen, "words": words}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    paras = [p.strip() for p in open(sys.argv[1], encoding="utf-8").read().split("\n\n") if p.strip()]
    r = render(paras, sys.argv[2])
    print(f"engine: elevenlabs {r['voice']} ({r['voice_name']}) model {r['model']}")
    print(f"credits: {r['credits']}{' (estimated)' if r['credits_estimated'] else ''}")
