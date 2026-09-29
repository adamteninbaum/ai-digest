# Daily Digest kit

A personal daily audio news brief that runs in **your own** Claude account. Pick your
topics, and every morning you get a private page with a 1 to 3 minute audio brief, the
full transcript with each word lighting up as it's read, direct links, and thumbs up/down
buttons that teach it what you like.

Sources: the web (Google News for your topics, Hacker News and Techmeme for tech, and a
few targeted searches) and, if you want, the newsletters already in your Gmail.

## Get started (about 10 minutes)
1. You need a paid Claude plan that includes Claude Code and Routines.
2. Open the intake form (https://claude.ai/artifact/TQZW7vQwws8rkmU7nkgCHi, once it is
   shared with you), answer the questions, and
   copy the setup message it gives you.
3. Go to claude.ai/code, start a new session, paste the message, and let Claude set
   everything up. It will tell you if you need to flip any settings (usually: turn on
   full network access for your cloud environment, and attach Gmail if you want your
   newsletters included).

## What's in here
- `RUNBOOK.md`: what your daily run does, step by step.
- `SETUP.md`: what Claude does when you paste your setup message.
- `PROFILE.md`: your preferences format.
- `site/index.html`: your digest page. `intake/index.html`: the intake form.
- `discover.py` (web news), `resolve_links.py` (clean links), `tts.py` (audio + word
  timings), `build_digest.py` (page files), `notify.py` and `dropbox_upload.py` (optional).

Everything runs on free services: Edge TTS for the voice and public news feeds. Your
brief runs on your own Claude usage.
