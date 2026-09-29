# AI Audio Digest: Routine runbook

This is the exact prompt the cloud Routine sends each firing. Keep it in sync with the
Routine (`mcp__Claude_Code_Remote__update_trigger`) if you edit it.

---

You are running Adam's AI Newsletter Audio Digest. Do every step; do not ask questions.
Recipient: adamshawn0102@gmail.com. Subject format: `AI Audio Digest - YYYY-MM-DD`.

## 1. Work out the window (state lives in Gmail, no state files)
- Gmail search `in:sent subject:"AI Audio Digest"` and take the newest one. Its date is the
  last successful run. If none exists, use the last 4 days.
- Read the last ~4 sent digests (get_thread, PLAIN_TEXT) and collect every URL in them.
  These are already-sent links; never send one again.

## 2. Fetch newsletters
- Query: `from:(news@daily.therundown.ai OR superhuman@mail.joinsuperhuman.ai OR dan@tldrnewsletter.com OR bensbites@substack.com OR post-training@mail.aitinkerers.org) after:<last run as YYYY/MM/DD>`
  then drop anything older than the exact last-run timestamp.
- Dedupe by subject line (The Rundown arrives twice, to adamshawn0102@ and
  solomon.m.teninbaum@). Read EVERY unique issue in full with PLAIN_TEXT (typically
  15 to 25 per window); do not sample or skim a subset. Wildcards come from the long tail.
- Ignore sponsor/ad blocks, job boards, referral and unsubscribe links.

## 3. Select 6 to 8 items
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

## 5. Script and audio
- Write a conversational script, roughly 90 seconds to 2 minutes (about 230 to 300 words).
  Not a list read aloud: each item gets a sentence or two on what it is and why it
  might matter to Adam. No URLs in the script.
- Render with Edge TTS:
  `pip install -q -r requirements.txt && python3 tts.py script.txt AI-Audio-Digest-YYYY-MM-DD.mp3`
  (`tts.py` is in the repo; it handles the cloud proxy's CA bundle).
- Save the MP3 to Dropbox and get a link:
  `python3 dropbox_upload.py AI-Audio-Digest-YYYY-MM-DD.mp3` (uploads to
  `/claude/ai_digest/`, prints a Dropbox shared link). It needs DROPBOX_APP_KEY,
  DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN, set on the cloud environment. The Dropbox
  connector cannot upload binary files, so this uses the Dropbox HTTP API.
- Fallback only if the Dropbox upload fails: commit the MP3 to `audio/` on the `audio`
  branch of adamteninbaum/ai-digest, push, and link
  `https://github.com/adamteninbaum/ai-digest/blob/audio/audio/<file>.mp3`.
- If TTS fails entirely, still send the email and say "Audio unavailable this run:
  <reason>" at the top.

## 5b. Clean the links
- Collect the original link for every chosen item, then run
  `python3 resolve_links.py URL1 URL2 ...`. It follows redirects (TLDR, Substack, AI
  Tinkerers and other tracking links), unwraps archive.superhuman.ai mirror pages to the
  original post, strips tracking params (utm_*, ref, _bhlid, jwt_token, fbclid, etc.), and
  falls back to the original URL (tracking params stripped) when a link cannot be resolved.
- Use the resolved URLs in the email, and compare resolved URLs when checking against
  already-sent links.

## 6. Deliver
Send one email with `send_message` (htmlBody plus a plain `body` fallback):
- Top line: "Listen (~2 min)" linking to the Dropbox shared link for the MP3.
- Then one bullet per item: a single line, the headline as a clickable link to the
  original article, then a short "why it matters" clause and
  the source newsletter in parentheses. Wildcards get a "Wildcard:" prefix. Links are the
  clean URLs from step 5b.
- Footer: window covered, number of newsletters read, and "Buzz = newsletter overlap
  (+ HN points when reachable)".

## 7. Finish
Reply in the session with a one-paragraph summary: items sent, audio status, anything
that failed.
