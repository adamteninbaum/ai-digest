# AI Audio Digest: Routine runbook

The cloud Routine clones this repo and follows this file step by step, so edits here take
effect on the next run. The Routine's own prompt only points here.

---

You are running Adam's AI Newsletter Audio Digest. Do every step; do not ask questions.
Recipient: adamshawn0102@gmail.com. Subject format: `AI Audio Digest - YYYY-MM-DD`.

## 1. Work out the window (state lives on the digest page, no state files)
The digest page is https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy (a private claude.ai Artifact Adam owns).
- `Artifact` action `read` with `url` = the page (required before you can republish it).
- `Artifact` action `read` with `url` = the page and `path` = `briefs/index.json`; it saves
  the file locally and tells you where. Keep that path for step 8.
- The newest entry whose `test` is not true: its `published_at` is the last successful
  run. If there is none, use the last 24 hours.
- Read the newest ~4 briefs (`path` = `briefs/<date>.json`) and collect every URL in their
  items. These are already-sent links; never send one again.

## 2. Fetch newsletters
- Query: `from:(news@daily.therundown.ai OR superhuman@mail.joinsuperhuman.ai OR dan@tldrnewsletter.com OR bensbites@substack.com OR post-training@mail.aitinkerers.org) after:<last run as YYYY/MM/DD>`
  then drop anything older than the exact last-run timestamp.
- Dedupe by subject line (The Rundown arrives twice, to adamshawn0102@ and
  solomon.m.teninbaum@). Read EVERY unique issue in full with PLAIN_TEXT (typically
  6 to 12 per daily window); do not sample or skim a subset. Wildcards come from the long tail.
- Ignore sponsor/ad blocks, job boards, referral and unsubscribe links.

## 3. Select 4 to 7 items (daily brief)
- Known lanes: 3D animation and motion design tooling; generative video and image models;
  VFX; creative production workflow; AI agents and automation; solo/small-business AI
  leverage; practical life hacks or clever workflow tricks of any kind.
- Wildcards: 2 or 3 genuinely novel, surprising, or clever items regardless of topic.
  Bias AGAINST the big story every newsletter ran; bias TOWARD the odd item only one
  newsletter noticed.
- If `preferences.md` exists in the adamteninbaum/ai-digest repo, read it and let it
  sharpen picks.

## 4. Buzz ranking (orders the list, never filters it)
- Cross-newsletter overlap: count how many distinct newsletters covered each story.
- Hacker News (free, no key): `https://hn.algolia.com/api/v1/search?query=<key terms>&tags=story&numericFilters=created_at_i><unix last run>`;
  use points + comments of the best match. Do this for every candidate item; only skip
  if the host is actually blocked, and say so in the footer.
- Reddit: not wired up yet (needs a free script-app credential). Skip.
- Order by buzz, but wildcards always survive.

## 5. Clean the links
- Collect the original link for every chosen item, then run
  `pip install -q -r requirements.txt && python3 resolve_links.py URL1 URL2 ...`. It
  follows redirects (TLDR, Substack, AI Tinkerers and other tracking links), unwraps
  archive.superhuman.ai mirror pages to the original post, strips tracking params
  (utm_*, ref, _bhlid, jwt_token, fbclid, etc.), and falls back to the original URL
  (tracking params stripped) when a link cannot be resolved.
- Use the resolved URLs everywhere below, and when checking against already-sent links.

## 6. Write the digest file (single source for the audio AND the page)
Write `digest.json` in the format documented at the top of `build_digest.py`:
- `intro`: one short spoken opening line.
- `items`: one entry per pick, in buzz order. `text` is exactly what will be spoken for
  that item: a sentence or two on what it is and why it might matter to Adam,
  conversational, no URLs. For wildcards, say so in the text ("Here's a wildcard...").
  `urls` holds the clean URL(s) from step 5. Include EVERY resource the spoken text
  points to, not just the article: if it mentions a prompt, repo, demo, video, tool or
  dataset that the newsletter linked, add that link too (resolved in step 5), as
  `{"url": "...", "label": "Detailed prompt"}` so Adam can tell the links apart. Plain
  strings are fine for the main article. `source` is the newsletter name(s); set
  `"wildcard": true` on wildcard items (the page tags them).
- `date`: today, YYYY-MM-DD. On a manual test run also set `"test": true`.
- `outro`: one short sign-off line.
- `footer`: window covered, issues read, "Buzz = newsletter overlap (+ HN points when
  reachable)".
- Total spoken length about 150 to 300 words (1 to 2 minutes). On a slow day use fewer
  items and a shorter script; never pad with weak picks.

## 7. Audio
- `python3 build_digest.py script digest.json` (writes script.txt), then
  `python3 tts.py script.txt AI-Audio-Digest-YYYY-MM-DD.mp3` (Edge TTS; handles the cloud
  proxy's CA bundle).
- Save it to Dropbox: `python3 dropbox_upload.py AI-Audio-Digest-YYYY-MM-DD.mp3`. It uploads
  to `/claude/ai_digest/` and prints a Dropbox shared link. It needs DROPBOX_APP_KEY,
  DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN, set on the cloud environment. The Dropbox
  connector cannot upload binary files, so this uses the Dropbox HTTP API.
- If the Dropbox upload fails, carry on without the Dropbox link (pass "" in step 8) and
  add "Dropbox upload failed: <reason>" to the footer. The page still plays the MP3,
  because step 8 publishes it alongside the page.
- If TTS fails entirely, see step 8 (`audio_note`).

## 8. Publish to the digest page (this replaces email)
Adam does not want email: the Gmail connector wraps every link in a Google redirect page.
- `python3 build_digest.py site digest.json out "<Dropbox link>" "<local path of the
  briefs/index.json you read in step 1>"` writes `out/briefs/<date>.json` and a merged
  `out/briefs/index.json`.
- Republish the page with the `Artifact` tool, action `publish`:
  `url` = https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy, `file_path` = `site/index.html` from this repo, and `files` =
  `{"briefs/index.json": "out/briefs/index.json", "briefs/<date>.json": "out/briefs/<date>.json",
  "audio/AI-Audio-Digest-<date>.mp3": "<the MP3 path>"}`. Do not pass `icon`,
  `capabilities` or `force`. Files you leave out (older briefs and audio) are kept.
- If TTS failed, set `"audio_note": "Audio unavailable this run: <reason>"` in digest.json
  and leave the MP3 out of `files`.
- Check it: `Artifact` action `list`, `scope` = `files`, `url` = the page; the new brief
  JSON and MP3 must be listed.
- Only if publishing fails: fall back to email. Run `python3 build_digest.py email
  digest.json "<Dropbox link>"` and send ONE email with Gmail `send_message` to
  adamshawn0102@gmail.com, subject `AI Audio Digest - YYYY-MM-DD (page publish failed)`,
  `htmlBody` = email.html, `body` = email.txt, verbatim.

## 9. Finish
Reply in the session with a one-paragraph summary that starts with the page link
(https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy): items sent, issues read, audio status
(Dropbox or fallback), links resolved vs fell back, HN status, anything that failed.
