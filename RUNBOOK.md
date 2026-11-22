# AI Audio Digest: Routine runbook

The cloud Routine clones this repo and follows this file step by step, so edits here take
effect on the next run. The Routine's own prompt only points here.

---

You are running Adam's AI Newsletter Audio Digest. Do every step; do not ask questions.
Adam is in US Eastern time: write every date and time that he will read (footer, window,
summary) in Eastern (ET), never UTC. `published_at` in index.json stays UTC (machine field).
Recipient: adamshawn0102@gmail.com. Subject format: `AI Audio Digest - YYYY-MM-DD`.

## 0. Repair mode ("Fix this brief")
If the Routine's run text starts with "REPAIR MODE", Adam tapped "Fix this brief" on the
page. Do ONLY this section, then stop. Do not fetch newsletters, do not run discovery,
do not make a new brief, and do not change any other brief.
- Get the brief id and "What to fix" from the run text.
- `pip install -q -r requirements.txt`. `Artifact` action `read` on the page (required
  before republishing), then read `briefs/index.json` and `briefs/<id>.json` with `path`.
- Rebuild `digest.json` from that brief JSON: keep `id`, `date`, `headline`, `intro`,
  `items` (with their `urls`, `source`, `media`, `wildcard`, and for saved articles `title`,
  `origin`, `saved`, `full`; do not re-render full-article audio), `outro`, `footer`. Drop
  `audio` and `timing` (they are regenerated).
- Fix what Adam asked for. Always also check these, whatever he wrote:
  - Audio: if the brief has no `audio.src`, run step 7 (`tts.py` falls back to the local
    Kokoro voice automatically if Edge TTS refuses). Only if both engines fail, keep
    `"audio_note"` with the new reason.
  - Links: if he names a bad link, re-resolve it with `resolve_links.py` or find the
    correct direct URL with WebSearch.
  - Voice: ALWAYS read his current pick (step 7's ArtifactData read). Re-render the
    audio with step 7 if the brief's `audio.voice` is missing or differs from the pick
    (for a pick of `edge_andrew`, `am_michael` counts as a match only if Edge still
    fails), or if he mentions the voice ("new voice", "re-record"). Set `voice` and a
    fresh `audio_rev` in digest.json either way you re-render.
  - Anything else he describes (wrong fact, item to drop, garbled wording): edit
    digest.json accordingly. If an item's spoken text changes, the audio must be
    re-rendered too.
- Publish exactly as in step 8 with the SAME id (`build_digest.py site` keeps the
  original `published_at` and adds `repaired_at`, so the next scheduled window is
  unaffected). Include the MP3 and any changed `media/...` files.
- No ntfy alert and no PushNotification for a repair. Finish with one line: "Brief <id>
  fixed: <what changed>" (or what could not be fixed and why).

## 0b. Saved-only mode ("Saved articles now")
If the run text starts with "SAVED ONLY MODE", Adam tapped "Saved articles now" on the page.
Make a brief with ONLY his new saved articles. Do not fetch newsletters, do not run
discovery or WebSearch, do not read votes or topics, and do not change other briefs.
- `pip install -q -r requirements.txt`. Step 1's first two bullets only (read the page, and
  `briefs/index.json`; keep its local path). Skip the window and the already-sent links.
- Step 2c in full (fetch, blurbs, items with `"origin": "saved"`).
- If there are no new saved articles: publish nothing. `ArtifactData` action `set`, `url` =
  the page, `collection` = `control`, `doc_id` = `saved_now`, `data` = `{"status": "none",
  "at": "<UTC now>"}` (read it first and pass its `version` as `if_version` if it exists), so
  the page tells Adam. No alerts. Finish with "Saved-only run: no new saved articles."
- Otherwise write digest.json as in step 6 with: `"kind": "saved"`, `intro` like "Hey Adam,
  here are the articles you saved.", the saved items only, a short `outro`, `headline` naming
  them, `footer` "Saved articles only. Newsletters come in the next daily brief." Get `id`
  with `nextid` as usual. No media (skip step 6b).
- Steps 7 and 8 as usual (brief audio, publish, both alerts; for notify.py use the article
  titles as the summary). Then set the same `control/saved_now` doc to `{"status": "done",
  "id": "<id>", "at": "<UTC now>"}`. The brief is now on the page.
- Then steps 8b (full-article audio) and 8c (share links), each added afterward with another publish.
- Finish with "Saved-only brief <id>: <n> articles" plus audio status and credits used.

## 1. Work out the window (state lives on the digest page, no state files)
The digest page is https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy (a private claude.ai Artifact Adam owns).
- `Artifact` action `read` with `url` = the page (required before you can republish it).
- `Artifact` action `read` with `url` = the page and `path` = `briefs/index.json`; it saves
  the file locally and tells you where. Keep that path for step 8.
- The newest entry whose `test` is not true AND whose `kind` is not `"saved"`: its
  `published_at` is the last successful run. (Saved-only briefs, section 0b, never move the
  newsletter window.) If there is none, use the last 24 hours.
- Read the newest ~4 briefs (`path` = `briefs/<id>.json`, where `<id>` is the entry's `id`,
  or its `date` for entries without one) and collect every URL in their
  items. These are already-sent links; never send one again.

## 2. Fetch newsletters
- Query: `from:(news@daily.therundown.ai OR superhuman@mail.joinsuperhuman.ai OR dan@tldrnewsletter.com OR bensbites@substack.com OR post-training@mail.aitinkerers.org) after:<last run as YYYY/MM/DD>`
  then drop anything older than the exact last-run timestamp.
- Forwarded newsletters: also search `after:<last run as YYYY/MM/DD> (subject:Fwd OR
  subject:Fw OR "Forwarded message" OR "Begin forwarded message") -in:sent`. Keep the ones
  whose forwarded content is a newsletter or article roundup (not personal threads,
  receipts or work requests), whatever the original sender, and name the original
  newsletter as the source (e.g. "Morning Brew, forwarded by Jamie").
- Dedupe by subject line, ignoring a leading "Fwd:"/"Fw:" (The Rundown arrives twice, to adamshawn0102@ and
  solomon.m.teninbaum@). Read EVERY unique issue in full with PLAIN_TEXT (typically
  6 to 12 per daily window); do not sample or skim a subset. Wildcards come from the long tail.
- Ignore sponsor/ad blocks, job boards, referral and unsubscribe links.

## 2b. Look online for what is hot right now (not just the newsletters)
- `pip install -q -r requirements.txt && python3 discover.py 24` (use the window length in
  hours if it is longer). It returns today's AI stories from Hacker News (with points and
  comments), Techmeme, Google News, Hugging Face's most upvoted papers and smol.ai's daily
  roundup when it is fresh. A source that fails is listed under `errors`; carry on.
- Also run 2 or 3 `WebSearch` queries such as "AI news today", "new AI model release
  this week", "AI video OR 3D animation tool launch" to catch anything big the feeds miss.
- Adam's topics: the page has a "More of this" box. Read it with `ArtifactData` action
  `list`, `url` = the digest page, `collection` = `interests` (each doc has `text`, e.g.
  "Apple AI, Siri agents", and `at`). For EACH topic run 1 `WebSearch` for news on it from
  the window (e.g. "<topic> news this week") and scan the newsletters for it too. If the
  read fails or the list is empty, skip this.
- These are CANDIDATES, judged exactly like newsletter items in steps 3 and 4. A story
  that is both in the newsletters and hot online gets a buzz boost. Aim for at least 1 or
  2 items per brief that came from online discovery and were NOT in the newsletters, when
  something good is there; label their `source` by where you found them (e.g.
  "Hacker News, 663 points" or "Techmeme").
- Google News links are Google wrappers: replace each with the publisher's own article
  URL (search the headline) before step 5. Techmeme links point at Techmeme's page; use
  the original article it cites. For Hacker News items, link the article and add the
  discussion as `{"url": "<HN thread>", "label": "HN discussion"}` when it is lively.
- Open (WebFetch) any online story you pick, so the spoken summary is accurate.

## 2c. Adam's saved articles (Apple News, via Dropbox)
His Mac saves each Apple News article he shares to Dropbox `/Claude/news-capture/articles/`
as a .txt (header lines Title, Source, Author, Date, Link; Author and Date may be missing).
EVERY new one becomes a story in this brief, on top of the 4 to 7 picks. Never use one twice.
- Already used: `Artifact` action `read`, `url` = the page, `path` = `saved/used.json`. Keep the
  local path as USED. If it does not exist yet (first run), use `""`.
- `python3 saved.py fetch <USED>`. It lists the folder with the Dropbox API keys on the
  environment and skips used files (by Dropbox file id, content hash and article link).
  - If it prints `NEED_LINKS id:... id:...` and exits 3 (the Dropbox app may list but not
    download), load the Dropbox connector tool `download_link` (ToolSearch
    `select:mcp__Dropbox__download_link`), call it with `entries` = those ids and
    `expiration_in_sec` = 900, Write its whole JSON result to `saved/links.json`, and run
    `python3 saved.py fetch <USED> saved/links.json`. The links are single use: do not open them.
  - If the Dropbox API itself fails (no keys, network): use the connector `list_folder` on
    `/Claude/news-capture/articles` (recursive false), then `download_link` on every `.txt`
    entry, and run the same `fetch <USED> saved/links.json`. The script still skips used ones.
- It writes `saved/new.json` and prints one line per new article. None new: skip the rest
  of this step and of step 8b.
- Read each new article in `saved/new.json` (title, source, author, paragraphs). For each,
  add one item to digest.json AFTER the regular picks (they do not count toward the 4 to 7):
  `{"text": "<spoken blurb>", "title": "<Title>", "urls": [{"url": "<Link>", "label":
  "Apple News"}], "source": "<Source>", "origin": "saved", "saved": "<key>"}`. The blurb is 2
  or 3 conversational sentences on what the piece says and why it is worth his time; start
  the first saved one with "From your saved articles:". The page marks it "Saved by Adam"
  and adds a "Listen to the full article" button. Do not run media.py links for these
  (apple.news pages have no useful media); leave `media` out.
- Saved articles skip the "already-sent links" and vote rules: Adam chose them.
- Mention them in the footer, e.g. "Saved articles: 2 (Vox, The Washington Post)".

## 3. Select 4 to 7 items (daily brief)
- Known lanes: 3D animation and motion design tooling; generative video and image models;
  VFX; creative production workflow; AI agents and automation; solo/small-business AI
  leverage; practical life hacks or clever workflow tricks of any kind.
- Wildcards: 2 or 3 genuinely novel, surprising, or clever items regardless of topic.
  Bias AGAINST the big story every newsletter ran; bias TOWARD the odd item only one
  newsletter noticed.
- Adam's votes: every item on the page has "More like this" / "Less like this" buttons.
  Read them before choosing: load the `ArtifactData` tool (ToolSearch
  `select:ArtifactData` if it is deferred), then action `list`, `url` = the digest page,
  `collection` = `feedback`. Each document has `vote` ("up" or "down"), the item's
  `text`, `source`, `urls`, `wildcard` and `date`. Page through all of them.
- Learn from them: find the patterns in what he liked (topics, kinds of item such as
  tools vs news vs how-tos, sources, wildcard style) and in what he disliked, and weight
  today's picks toward the liked patterns and away from the disliked ones. Newer votes
  count more than older ones. Keep 2 or 3 wildcards regardless, but shape them by the
  wildcard votes. Never repeat an item he already voted on.
- Adam's topics (step 2b): any real, recent story matching one of his topics gets a
  strong boost; include the best match whenever one exists, even if the newsletters
  missed it. Don't force a stale or weak match in. Note matches in the footer (e.g.
  "Topics matched: Apple AI").
- If the feedback read fails, carry on without it and say so in the footer. Mention in
  the footer how many votes informed the picks (e.g. "Shaped by 12 votes: 9 up, 3 down").
- `preferences.md` in the repo holds any standing preferences; read it too.

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
- Do not number items in their text. `build_digest.py script` adds the spoken number
  ("One, ...", "Two, ...") to the audio automatically; the page shows 01, 02.
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
- `origin` on every item, so the page can badge it: `"gmail"` if it came from a newsletter
  in Adam's Gmail (forwarded ones too), `"web"` if it came only from online discovery
  (step 2b), `"both"` if it was in a newsletter AND hot online.
- `media_urls` (optional): if the newsletter or article points to an interesting image,
  demo video, X post with a video, or YouTube video for this item, list those links here
  (resolved). Step 6b tries them first, then the item's `urls`.
- `date`: today, YYYY-MM-DD. On a manual test run also set `"test": true`.
- `id`: run `python3 build_digest.py nextid "<local briefs/index.json from step 1>" <date>`
  and use what it prints (the date, or date-2, date-3... if today already has a brief).
  Existing briefs are never replaced. Use `<id>` in every file name below.
- `outro`: one short sign-off line.
- `footer`: window covered, issues read, "Buzz = newsletter overlap (+ HN points when
  reachable)".
- Total spoken length about 150 to 300 words (1 to 2 minutes). On a slow day use fewer
  items and a shorter script; never pad with weak picks.

## 6b. Images and video (shown right in the brief)
- `python3 media.py digest.json` finds one image or video per item (from `media_urls`,
  then the article pages: X posts, YouTube, og:image/og:video, `<video>` tags), saves it
  under `media/`, writes `media` into each item in digest.json, and prints the `files`
  entries for step 8. Videos up to 14 MB play on the page; YouTube and bigger videos show
  as a poster that opens the video.
- Look at every saved image (Read the .jpg) and keep only ones worth seeing: product shots,
  demo stills, screenshots, charts, diagrams, real photos of the thing. Drop logos, generic
  social cards, stock photos and headshots: set that item's `"media": []` in digest.json and
  leave its files out of step 8. Keep every playable video unless it is clearly unrelated.
- If it fails, carry on without media and say so in the step 9 summary.

## 7. Audio
- Adam's voice pick: `ArtifactData` action `get`, `url` = the page, `collection` =
  `control`, `doc_id` = `voice`. Use its `voice` field as VOICE_ID (e.g. `edge_andrew`,
  `am_michael`, `bm_george`, `af_heart`). If the doc is missing or the read fails, use
  `edge_andrew`.
- `python3 build_digest.py script digest.json` (writes script.txt), then
  `python3 tts.py script.txt AI-Audio-Digest-<id>.mp3 <VOICE_ID>` (Edge TTS, retried 3 times; if
  Microsoft refuses it falls back to the local Kokoro voice automatically and prints
  `engine: kokoro`. Say which engine was used in the step 9 summary). It also writes `AI-Audio-Digest-<id>.words.json`, the timing of
  every spoken word, which the page uses to highlight words as they are read.
- Do NOT upload to Dropbox. Adam no longer wants Dropbox copies; the MP3 lives only on
  the digest page (step 8).
- tts.py prints `voice_used: <id>` (the voice actually spoken, e.g. `am_michael` when
  Andrew fell back). Put it in digest.json as `"voice": "<id>"`, and set `"audio_rev"`
  to the current UTC time (e.g. `"2026-10-13T03:01:00Z"`) so phones fetch the new file
  instead of a cached one.
- If TTS fails entirely, see step 8 (`audio_note`).

## 8. Publish to the digest page (this replaces email)
Adam does not want email: the Gmail connector wraps every link in a Google redirect page.
- `python3 build_digest.py site digest.json out "" "<local path of the
  briefs/index.json you read in step 1>" AI-Audio-Digest-<id>.words.json` writes
  `out/briefs/<id>.json` (with word timings) and a merged `out/briefs/index.json`.
- Republish the page with the `Artifact` tool, action `publish`:
  `url` = https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy, `file_path` = `site/index.html` from this repo, and `files` =
  `{"briefs/index.json": "out/briefs/index.json", "briefs/<id>.json": "out/briefs/<id>.json",
  "audio/AI-Audio-Digest-<id>.mp3": "<the MP3 path>"}` plus every `media/...` entry step 6b
  printed and you kept. If step 2c found new saved articles, first run `python3 saved.py
  mark <USED from step 2c>` and add the `saved/used.json` entry it prints: it stops an article
  being used twice, so it goes in the same publish as the brief. Do not pass `icon`,
  `capabilities` or `force`. Files you leave out (older briefs and audio) are kept.
- If TTS failed, set `"audio_note": "Audio unavailable this run: <reason>"` in digest.json
  and leave the MP3 out of `files`.
- Check it: `Artifact` action `list`, `scope` = `files`, `url` = the page; the new brief
  JSON and MP3 must be listed.
- Phone alert: Adam gets alerts in the Claude iPhone app. Once the publish is confirmed,
  load the `PushNotification` tool (ToolSearch `select:PushNotification`) and send one
  line under 200 characters, e.g. "AI digest ready: <top story> + <n-1> more. Open the
  AI Audio Digest page." If it says not sent, carry on: the Routine's own phone alert
  fires when the run ends, and it shows the step 9 summary.
- REQUIRED on every run, scheduled or on-demand ("New brief now"): send the ntfy alert
  (a banner that opens this brief directly when tapped):
  `python3 notify.py <id> "<the top 2 stories in plain words>" <item count>`. It must print
  `sent <id>`. If it fails, retry once. Never skip it, even for a short or on-demand brief.
- Also send the PushNotification above. If either alert fails, note it in the step 9
  summary and carry on.
- Only if publishing fails: fall back to email. Run `python3 build_digest.py email
  digest.json "https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy"` (the page, as the listen link) and send ONE email with Gmail `send_message` to
  adamshawn0102@gmail.com, subject `AI Audio Digest - YYYY-MM-DD (page publish failed)`,
  `htmlBody` = email.html, `body` = email.txt, verbatim.

Then do steps 8b and 8c if step 2c found new saved articles.

## 8b. Full-article audio for saved articles (AFTER step 8; only if step 2c found new ones)
The brief is already published and the alerts sent. This adds the "Listen to the full article"
button afterward, so the slow full-article audio never holds up the brief.
- Full-article voice: `ArtifactData` action `get`, `url` = the page, `collection` =
  `control`, `doc_id` = `article_voice`. Its `mode` is `default` (Adam's brief voice, free),
  `elevenlabs` (ElevenLabs instead), `both` (both, to compare) or `sample` (brief voice for
  the whole article plus a short ElevenLabs clip of the first minute, about 1,000 credits)
  or `off` (no full-article audio: stop here). Pass the mode to render as is. Missing or
  failed read: `default`.
- `python3 saved.py render <VOICE_ID from step 7> <mode> <USED from step 2c>`. It renders
  each new article's full text (the brief voice, and/or ElevenLabs via elevenlabs_tts.py),
  writes `out/briefs/full/<key>.json` with word timings and the MP3s under `audio_full/`.
  Its LAST stdout line is a JSON map of Artifact `files` entries.
- Then add the button: `python3 build_digest.py site digest.json out "" out/briefs/index.json
  AI-Audio-Digest-<id>.words.json` (the index step 8 wrote; this keeps the brief's
  `published_at`), and publish again exactly as in step 8 with `files` = `briefs/index.json`,
  `briefs/<id>.json` and every entry render printed. No alerts this time.
- Kokoro is slow on this machine (about 7 minutes per 1,000 words), so render stops safely
  after about 8 minutes and prints `PARTIAL ...` (exit code 4). Use a Bash timeout of
  600000 ms and run the SAME command again until it prints the files map. Finished
  paragraphs, versions and ElevenLabs audio are cached and never redone (no double credits).
  Two long articles can take 30 minutes or more; that is expected.
- ElevenLabs needs the network secret for `api.elevenlabs.io` (header `xi-api-key`) on the
  cloud environment; the proxy adds the key. If it fails, the script records a note (and for
  `elevenlabs` mode falls back to the brief voice); say so in the step 9 summary with the
  credits used (`credits` in each version).
- If the full-article audio fails, leave the brief as it is (it is already published).

## 8c. Share with friends & family (AFTER step 8b; for every new saved article)
Adam wants a "Share with friends & family" button on every saved article. Each one gets a
public Dropbox folder `/Claude/news-capture/shared/<date> <title>/` with the article as a PDF
(text plus lead image), a plain text copy (`<title> (text).txt`) and its full audio; the page
shows the button when an item has
`full.share`.
- `python3 -m pip install -q reportlab && python3 -m pip install -q --ignore-installed Pillow`
  (an old system Pillow can break the PDF step), then
  `python3 share.py out/briefs/<id>.json` (after 8b, so the full audio exists; run it even if
  8b failed: the PDF still gets made). It skips items that already have a link, prints one line
  per article and `shared N`.
- Then publish once more exactly as in step 8b (`briefs/<id>.json` only is enough). No alerts.
- If it fails (Dropbox keys, network), the brief stays as it is; say so in the step 9 summary.
  Never drop a share link that is already on an item.

## 9. Finish
This summary is what Adam's phone alert shows, so its first line must be "AI digest
ready:" plus the top 2 stories in a few words. Then reply with a one-paragraph summary that
starts with the page link
(https://claude.ai/artifact/F5KSHeyUzh53AbRktU8ozy): items sent, issues read, audio status
(on the page or failed), media (how many items got an image or video), saved articles (how
many, full-audio voice per article, ElevenLabs credits used), ntfy (the `sent` id, or why it failed), links resolved vs fell back, HN status, anything that failed.
