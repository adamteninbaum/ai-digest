# ai-digest

Adam's AI Newsletter Audio Digest, run as a Claude Code cloud Routine every day at 11am Eastern (starts 10:52am) and
published to a private claude.ai page: https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy

- `RUNBOOK.md`: the prompt the Routine runs (fetch via Gmail connector, select, rank,
  script, Edge TTS, Dropbox, page publish). State lives in the page's briefs/index.json.
- `tts.py`: Edge TTS renderer that works behind the cloud session proxy; also saves
  per-word timings so the page highlights each word as it is spoken.
- `site/index.html`: the digest page. It reads `briefs/index.json`, `briefs/<date>.json`
  and `audio/*.mp3`, which each run publishes alongside it.
- `build_digest.py`: turns digest.json into the TTS script, the page's brief files, and
  (fallback only) an email.
- `discover.py`: today's hot AI stories online (Hacker News, Techmeme, Google News,
  Hugging Face papers, smol.ai), judged alongside the newsletters.
- `resolve_links.py`: follows tracking redirects and strips tracking params.
- `dropbox_upload.py`: uploads the MP3 to Dropbox `/claude/ai_digest/` and prints a shared link.
- `notify.py`: ntfy phone alert that opens the new brief when tapped (sent every run,
  alongside the Claude app alert).
- `preferences.md`: optional feedback the selection step reads each run.
- Audio goes to Dropbox; the `audio` branch is only a fallback if Dropbox fails.

Environment variables (cloud environment settings): `DROPBOX_APP_KEY`,
`DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`.

Network hosts the cloud environment must allow: `speech.platform.bing.com` (Edge TTS),
`hn.algolia.com` (buzz, optional).
