"""Render a digest script to MP3, plus word timings for the page.

Usage: python3 tts.py SCRIPT.txt OUT.mp3 [VOICE_ID]
VOICE_ID is Adam's pick from the page's voice picker (db doc control/voice):
"edge_andrew" (default) or a Kokoro voice id such as "am_michael", "bm_george", "af_heart".
Writes OUT.mp3 and OUT.words.json: [{"text": "Hey", "start": 50, "end": 310}, ...] in
milliseconds, one entry per spoken word, which build_digest.py turns into the page's
word-by-word highlighting.

With "edge_andrew" (or any id ending in "Neural"), engines in order:
1. Edge TTS (Microsoft neural voice). Tried 3 times with backoff. Microsoft's free
   endpoint sometimes refuses connections (HTTP 403) for hours at a time.
2. Kokoro (open model, runs on this machine's CPU, no network needed once the ~120 MB
   model is downloaded from GitHub). Word timings are estimated per paragraph.
Any Kokoro voice id skips Edge and renders with that voice directly.
Set TTS_ENGINE=kokoro to skip Edge. The last stdout line is "engine: edge" or
"engine: kokoro"; the script exits non-zero only if both fail.

Works inside Claude Code cloud sessions: edge_tts pins certifi's CA store, so we
swap in the proxy CA bundle (if present) and pass HTTPS_PROXY through explicitly.
"""
import asyncio
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request

EDGE_VOICE = "en-US-AndrewMultilingualNeural"
KOKORO_VOICE = "am_michael"
KOKORO_DIR = os.path.expanduser("~/.cache/kokoro")
KOKORO_FILES = {
    "kokoro-v1.0.int8.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
CA = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"


def words_path(out):
    return os.path.splitext(out)[0] + ".words.json"


# ---------- Edge TTS ----------
async def edge_once(text, out, voice):
    import edge_tts
    import edge_tts.communicate as comm
    if os.path.exists(CA):
        comm._SSL_CTX = ssl.create_default_context(cafile=CA)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    tts = edge_tts.Communicate(text, voice, rate="+5%", proxy=proxy, boundary="WordBoundary")
    words, size = [], 0
    with open(out, "wb") as fh:
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
                size += len(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10000  # 100 ns ticks -> ms
                words.append({"text": chunk["text"], "start": round(start),
                              "end": round(start + chunk["duration"] / 10000)})
    if size < 1000:
        raise RuntimeError("Edge TTS returned no audio")
    with open(words_path(out), "w", encoding="utf-8") as fh:
        json.dump(words, fh, ensure_ascii=False)


def edge(text, out, voice):
    last = None
    for wait in (0, 5, 20):
        time.sleep(wait)
        try:
            asyncio.run(edge_once(text, out, voice))
            return
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"edge attempt failed: {str(e)[:120]}", file=sys.stderr)
    raise RuntimeError(f"Edge TTS failed 3 times: {str(last)[:120]}")


# ---------- Kokoro (local) ----------
def kokoro_model():
    os.makedirs(KOKORO_DIR, exist_ok=True)
    paths = []
    for name, url in KOKORO_FILES.items():
        p = os.path.join(KOKORO_DIR, name)
        if not os.path.exists(p) or os.path.getsize(p) < 1_000_000:
            ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else None
            with urllib.request.urlopen(url, context=ctx, timeout=300) as r, open(p + ".part", "wb") as fh:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    fh.write(b)
            os.replace(p + ".part", p)
        paths.append(p)
    return paths


def kokoro(text, out, voice=KOKORO_VOICE):
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages",
                        "kokoro-onnx", "soundfile"], check=True)
        from kokoro_onnx import Kokoro
    import numpy as np
    import soundfile as sf

    model, voices = kokoro_model()
    k = Kokoro(model, voices)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    gap_s = 0.35
    chunks, words, t, sr = [], [], 0.0, 24000
    for para in paragraphs:
        samples, sr = k.create(para, voice=voice, speed=1.05,
                               lang="en-gb" if voice.startswith("b") else "en-us")
        dur = len(samples) / sr
        # Estimate word timings: spread the paragraph's duration by word length.
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
    wav = os.path.splitext(out)[0] + ".wav"
    sf.write(wav, np.concatenate(chunks), sr)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-codec:a", "libmp3lame",
                    "-b:a", "64k", out], check=True)
    os.remove(wav)
    with open(words_path(out), "w", encoding="utf-8") as fh:
        json.dump(words, fh, ensure_ascii=False)


def main(src, out, voice):
    text = open(src, encoding="utf-8").read().strip()
    voice = (voice or "edge_andrew").strip()
    edge_voice = EDGE_VOICE if voice.startswith("edge_") else voice if voice.endswith("Neural") else None
    if edge_voice and os.environ.get("TTS_ENGINE", "").lower() != "kokoro":
        try:
            edge(text, out, edge_voice)
            print(f"engine: edge {edge_voice}")
            print("voice_used: edge_andrew")
            return
        except Exception as e:  # noqa: BLE001
            print(f"{e}; falling back to Kokoro", file=sys.stderr)
    kv = KOKORO_VOICE if edge_voice else voice
    kokoro(text, out, kv)
    print(f"engine: kokoro {kv}")
    print(f"voice_used: {kv}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "edge_andrew")
