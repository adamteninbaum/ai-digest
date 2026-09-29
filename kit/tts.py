"""Render a digest script to MP3 with Edge TTS, plus word timings for the page.

Usage: python3 tts.py SCRIPT.txt OUT.mp3 [VOICE]
Writes OUT.mp3 and OUT.words.json: [{"text": "Hey", "start": 50, "end": 310}, ...] in
milliseconds, one entry per spoken word, which build_digest.py turns into the page's
word-by-word highlighting.

Works inside Claude Code cloud sessions: edge_tts pins certifi's CA store, so we
swap in the proxy CA bundle (if present) and pass HTTPS_PROXY through explicitly.
"""
import asyncio
import json
import os
import ssl
import sys

import edge_tts
import edge_tts.communicate as comm

CA = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(CA):
    comm._SSL_CTX = ssl.create_default_context(cafile=CA)

VOICE = "en-US-AndrewMultilingualNeural"


async def main(src, out, voice):
    text = open(src, encoding="utf-8").read().strip()
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    tts = edge_tts.Communicate(text, voice, rate="+5%", proxy=proxy, boundary="WordBoundary")
    words = []
    with open(out, "wb") as fh:
        async for chunk in tts.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10000  # 100 ns ticks -> ms
                words.append({"text": chunk["text"], "start": round(start),
                              "end": round(start + chunk["duration"] / 10000)})
    with open(os.path.splitext(out)[0] + ".words.json", "w", encoding="utf-8") as fh:
        json.dump(words, fh, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else VOICE))
