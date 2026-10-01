# Daily Digest: run runbook

Each person's daily Routine clones this repo and follows this file step by step. Everything
personal (name, topics, sources, number of items, voice, time zone) comes from the
**profile** saved on that person's own digest page, so this file is the same for everyone.

---

You are making one person's daily audio news brief. Do every step; do not ask questions.
The Routine prompt gives you `PAGE_URL` (their private digest page). Everything else comes
from the profile you read in step 1.

## 1. Read the page, the profile and the history
- `Artifact` action `read` with `url` = PAGE_URL (required before you can republish it).
- Load the `ArtifactData` tool (ToolSearch `select:ArtifactData` if it is deferred) and
  `get` collection `config`, doc_id `profile`. That JSON is the profile (format in
  `PROFILE.md`). If it cannot be read, use the profile copy in the Routine prompt, and say
  so in the footer.
- Write every date and time the person will read (footer, window, summary) in the
  profile's `timezone`, labeled with `timezone_label` (e.g. "ET"). `published_at` stays UTC.
- `Artifact` action `read`, `url` = PAGE_URL, `path` = `briefs/index.json`. It saves the
  file locally; keep that path for step 8. If it does not exist yet, this is the first
  brief: use the last 24 hours and an empty history.
- The newest entry whose `test` is not true: its `published_at` is the last run; the
  window is from then until now (at most 3 days). Otherwise use the last 24 hours.
- Read the newest ~4 briefs (`path` = `briefs/<id>.json`) and collect every URL in them.
  Never send one again.
- Their votes: `ArtifactData` `list` collection `feedback` (page through all). Each
  document has `vote` ("up"/"down") and the item's `text`, `source`, `urls`, `wildcard`,
  `date`. Newer votes count more. Never repeat an item they voted on.

## 2. Newsletters (only if `sources.newsletters` or `sources.outlook` is true)
Do 2a, 2b or both, then 2c.

### 2a. Gmail (only if `sources.newsletters` is true)
- Needs the Gmail connector on this Routine. If Gmail tools are missing, skip this step
  and put "Gmail skipped: Gmail isn't connected to this Routine" in the footer.
- If `sources.newsletter_senders` lists addresses, search
  `from:(a@x.com OR b@y.com) after:<window start YYYY/MM/DD>`.
  Otherwise find newsletters automatically: search
  `after:<window start YYYY/MM/DD> unsubscribe -in:sent -in:chats -category:social`,
  skim the results (MINIMAL format) and keep the ones that are clearly editorial
  newsletters (not receipts, shipping, promos, security alerts or personal mail).
- Read kept issues with PLAIN_TEXT.

### 2b. Outlook (only if `sources.outlook` is true)
- Needs the Microsoft 365 connector on this Routine (tools named like
  `outlook_email_search` and `read_resource`). If they are missing, skip this step and
  put "Outlook skipped: Microsoft 365 isn't connected to this Routine" in the footer.
- This is often a work mailbox. Use ONLY editorial newsletters from outside senders:
  skip anything from their own organization's domain (the domain of their own address; the connector's `get_me` tool gives it),
  and anything addressed to them personally, internal, confidential, or about work
  they are doing. Never mention, quote or summarize such mail anywhere.
- If `sources.newsletter_senders` lists addresses, run `outlook_email_search` once per
  sender with `sender` = the address and `afterDateTime` = window start (ISO), `limit` 25.
  Otherwise find newsletters automatically: `outlook_email_search` with
  `query` = "unsubscribe", `afterDateTime` = window start, `limit` 25; follow `nextOffset`
  (as `offset`) for up to 4 pages. Do not pass `folderName` or `order`. Keep the ones that
  are clearly editorial newsletters (not receipts, shipping, promos, security alerts,
  calendar or personal mail).
- Read kept issues with `read_resource` on each email's `mail:///messages/...` URI.

### 2c. For all newsletters
- Forwarded newsletters (unless `sources.include_forwarded` is false): also search
  `after:<window start YYYY/MM/DD> (subject:Fwd OR subject:Fw OR "Forwarded message" OR
  "Begin forwarded message") -in:sent`. Keep the ones whose forwarded content is a
  newsletter or article digest (not a personal thread or a work request), and treat
  the ORIGINAL newsletter inside as the source (name it, e.g. "Morning Brew, forwarded
  by Jamie"). Their links work like any newsletter's.
- Drop anything older than the exact window start. Dedupe by subject line (ignore a
  leading "Fwd:"/"Fw:"), so a forward of an issue you already have is not counted twice.
- Read EVERY kept issue in full; no sampling. Ignore sponsor blocks, job
  boards, referral and unsubscribe links.

## 3. Web discovery (only if `sources.web` is true, which is the default)
- `pip install -q -r requirements.txt && python3 discover.py --topics "<topics joined by
  commas, plus any specific interests worth their own search>" --hours <window hours>`
  (add `--local "<local_area>"` if the profile has one).
- Also run 2 to 4 `WebSearch` queries built from the profile's `interests` (their own
  words), e.g. "<interest> news this week", to catch what the feeds miss.
- Google News links are Google wrappers: replace each with the publisher's own article
  URL (search the headline). Techmeme links point at Techmeme; use the article it cites.
  For Hacker News items, add the thread as `{"url": "...", "label": "HN discussion"}`.
- Open (WebFetch) any story you pick, so the spoken summary is accurate.

## 4. Choose the items
- Exactly `items` picks when there is enough good material, fewer on a slow day; never
  pad. Of these, `wildcards` are wildcards: genuinely novel, surprising or clever items
  outside their stated topics that they would still enjoy. Bias AGAINST the one big story
  everyone ran; bias TOWARD the odd item only one source noticed.
- The rest match their `topics` and `interests`. Respect `avoid` strictly.
- Use the votes from step 1: lean toward the patterns they liked (topics, kinds of item
  such as news vs tools vs how-tos, sources, wildcard style) and away from what they didn't.
- Order by buzz: how many sources covered it, plus Hacker News points where relevant.
  Wildcards always survive.

## 5. Clean the links
`python3 resolve_links.py URL1 URL2 ...` follows tracking redirects, unwraps mirror pages,
strips tracking parameters, and falls back to the original. Use the clean URLs below and
when checking against already-sent links.

## 6. Write digest.json (one source for the audio AND the page)
Format documented at the top of `build_digest.py`:
- `intro`: one short spoken line that greets them by `name`.
- `items`: in buzz order. `text` is exactly what will be spoken: a sentence or two on what
  it is and why it might matter to THIS person, in the profile's `tone`, no URLs. Say
  "Here's a wildcard..." for wildcards and set `"wildcard": true`. `urls`: the clean
  article URL, plus EVERY resource the text points to (a prompt, repo, recipe, video,
  tool...) as `{"url": "...", "label": "Recipe"}`. `source`: where it came from.
- `outro`: one short sign-off.
- `date`: today in their time zone. `id`: `python3 build_digest.py nextid "<index.json
  path from step 1, or an empty string>" <date>`. On a manual test run set `"test": true`.
- `footer`: window covered (their time zone), sources read, how many picks came from the
  web vs newsletters, and "Shaped by N votes" (or "no votes yet").
- Total spoken length about `audio_minutes` minutes (about 150 words per minute).

## 7. Audio
- `python3 build_digest.py script digest.json`, then
  `python3 tts.py script.txt Digest-<id>.mp3 <voice>` (writes the MP3 and
  `Digest-<id>.words.json`, the per-word timings the page uses for highlighting).
- If `dropbox` is true and DROPBOX_APP_KEY, DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN
  are set: `python3 dropbox_upload.py Digest-<id>.mp3` and keep the printed link.
  Otherwise use "" for the Dropbox link.
- If TTS fails (usually the network blocks speech.platform.bing.com): set
  `"audio_note": "Audio unavailable: turn on full internet access for this environment"`
  in digest.json and publish the text anyway.

## 8. Publish
- `python3 build_digest.py site digest.json out "<Dropbox link or empty>" "<index.json path
  from step 1, or empty>" Digest-<id>.words.json`
- `Artifact` publish: `url` = PAGE_URL, `file_path` = `site/index.html` from this repo,
  `files` = `{"briefs/index.json": "out/briefs/index.json", "briefs/<id>.json":
  "out/briefs/<id>.json", "audio/AI-Audio-Digest-<id>.mp3": "Digest-<id>.mp3"}`.
  (The page expects the audio at `audio/AI-Audio-Digest-<id>.mp3`.) Do not pass `icon`,
  `capabilities` or `force`. Older briefs and audio are kept.
- Verify with `Artifact` action `list`, `scope` = `files`, `url` = PAGE_URL.
- Alerts: send a `PushNotification` (ToolSearch `select:PushNotification`): "Your daily
  digest is ready: <top story> + <n-1> more." If `alerts.ntfy_topic` is set, also run
  `python3 notify.py <ntfy_topic> <PAGE_URL> "<top 2 stories>" <item count>`.

## 9. Finish
First line: "Daily digest ready:" plus the top 2 stories in a few words (this is what the
phone alert shows). Then one paragraph starting with PAGE_URL: items published (web vs
newsletters), sources read, votes used, audio status, anything that failed.
