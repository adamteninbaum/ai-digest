# ai-digest

Adam's AI Newsletter Audio Digest, run as a Claude Code cloud Routine every 3 days.

- `RUNBOOK.md`: the prompt the Routine runs (fetch via Gmail connector, select, rank,
  script, Edge TTS, email delivery). State lives in Gmail's Sent folder, not in files.
- `tts.py`: Edge TTS renderer that works behind the cloud session proxy.
- `resolve_links.py`: follows tracking redirects and strips tracking params.
- `dropbox_upload.py`: uploads the MP3 to Dropbox `/claude/ai_digest/` and prints a shared link.
- `preferences.md`: optional feedback the selection step reads each run.
- Audio goes to Dropbox; the `audio` branch is only a fallback if Dropbox fails.

Environment variables (cloud environment settings): `DROPBOX_APP_KEY`,
`DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`.

Network hosts the cloud environment must allow: `speech.platform.bing.com` (Edge TTS),
`hn.algolia.com` (buzz, optional).
