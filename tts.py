"""Render a digest script to MP3 with Edge TTS.

Usage: python3 tts.py SCRIPT.txt OUT.mp3 [VOICE]

Works inside Claude Code cloud sessions: edge_tts pins certifi's CA store, so we
swap in the proxy CA bundle (if present) and pass HTTPS_PROXY through explicitly.
"""
import asyncio
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
    await edge_tts.Communicate(text, voice, rate="+5%", proxy=proxy).save(out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else VOICE))
