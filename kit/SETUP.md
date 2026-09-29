# Setup: instructions for Claude

A person pasted a setup message from the Daily Digest intake form into Claude Code. It
contains their profile JSON. Follow these steps in order, then report back in plain words.
Do not ask them questions unless a step cannot continue without their answer.

## 1. Get the kit
`git clone https://github.com/adamteninbaum/daily-digest-kit /tmp/daily-digest-kit`
(public repo; no login needed). Work from that folder.

## 2. Check the network
Run `curl -s -o /dev/null -w '%{http_code}' https://speech.platform.bing.com/ ; echo;
curl -s -o /dev/null -w '%{http_code}' https://news.google.com/rss ; echo`.
If either prints 000 or 403, their cloud environment blocks the voice or news services.
Carry on with setup, but in step 8 tell them to turn on **Full** network access: in a
Claude Code session, open the session title menu, choose **Edit cloud environment**,
set **Network access** to Full, and save. Their daily Routine uses the same environment.

## 3. Publish their digest page
Read `site/index.html` in full, then publish it with the `Artifact` tool (action
`publish`): `file_path` = `site/index.html`, `icon` = `audio`, `description` = "My daily
audio news brief", `capabilities` =
`{"db": {}, "mcp": {"servers": [{"server": "Claude Code Remote", "tools": ["fire_trigger"]}]}}`.
Keep the URL it returns: that is PAGE_URL.

## 4. Create their daily Routine
Use `create_trigger` (claude-code-remote tools; load with ToolSearch if deferred):
- `name`: "<name>'s Daily Digest"
- `create_new_session_on_fire`: true
- `notifications`: `{"push": true}`
- `cron_expression`: `CRON_TZ=<timezone> <MM> <HH> * * *`, where HH:MM is 8 minutes
  before the profile's `time` (so the brief is ready on time).
- `connectors`: `["Gmail"]` if `sources.newsletters` is true. If the call refuses
  connectors, create it without them and tell them in step 8 to attach Gmail to the
  Routine in claude.ai (Claude Code, Routines, their digest Routine, Connectors).
- `initiation`: `human_request`
- `prompt` (fill in the two blanks):

```
You are making <name>'s daily audio news brief. Do every step; do not ask questions.
Clone https://github.com/adamteninbaum/daily-digest-kit (public; git clone needs no login)
and follow its RUNBOOK.md exactly.
PAGE_URL = <PAGE_URL>
Backup copy of the profile (the live one is saved on the page as config/profile):
<profile JSON>
```
Keep the trigger id it returns.

## 5. Save the profile on the page
Add `page_url` and `trigger_id` to the profile, then `ArtifactData` action `set`,
`url` = PAGE_URL, `collection` = `config`, `doc_id` = `profile`, `data` = the profile.
(Load ArtifactData with ToolSearch if deferred.)

## 6. Make the first brief
`fire_trigger` with the trigger id. It takes about 5 minutes.

## 7. Optional extras
- ntfy alerts: if `alerts.ntfy_topic` is set, tell them to install the free **ntfy** app
  and subscribe to that exact topic.
- Dropbox copies of the audio: only if they ask; see `dropbox_upload.py`.

## 8. Tell them, briefly
- Their page link (PAGE_URL), and that the first brief appears there in about 5 minutes.
- Any fixes from steps 2 and 4 they need to do (network access, attaching Gmail).
- How to use it: press play (each word lights up as it is read), vote "More like this" /
  "Less like this" to teach it, "New brief now" for an extra one (allow the permission
  the first time), and "All briefs" for past days.
- For a phone icon: open the page in Safari, Share, Add to Home Screen.
- To change preferences later: fill in the intake form again and paste the new message
  into a Claude Code session with "Update my Daily Digest profile" (steps 4 and 5 only:
  update the Routine's schedule and prompt with `update_trigger`, and re-save the profile).
