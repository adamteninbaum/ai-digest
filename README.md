# ai-digest

Adam's AI Newsletter Audio Digest, run as a Claude Code cloud Routine every 3 days.

- `RUNBOOK.md`: the prompt the Routine runs (fetch via Gmail connector, select, rank,
  script, Edge TTS, email delivery). State lives in Gmail's Sent folder, not in files.
- `tts.py`: Edge TTS renderer that works behind the cloud session proxy.
- `preferences.md`: optional feedback the selection step reads each run.
- Audio files are pushed to the `audio` branch, under `audio/`.

Network hosts the cloud environment must allow: `speech.platform.bing.com` (Edge TTS),
`hn.algolia.com` (buzz, optional).
