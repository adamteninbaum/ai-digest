# Profile format

Each person's preferences, saved on their own digest page (database doc `config/profile`)
and copied into their Routine prompt as a backup. The intake form writes this for you.

```json
{
  "name": "Sam",
  "topics": ["AI", "Basketball", "Cooking"],
  "interests": "In my own words: the Knicks, one-pan dinners, AI tools for small business",
  "avoid": "celebrity gossip, crypto price talk",
  "local_area": "Chicago",
  "sources": {
    "web": true,
    "newsletters": true,
    "outlook": false,
    "newsletter_senders": ["dan@tldrnewsletter.com"],
    "include_forwarded": true
  },
  "items": 6,
  "wildcards": 2,
  "audio_minutes": 2,
  "voice": "en-US-AndrewMultilingualNeural",
  "tone": "conversational and a little playful",
  "time": "07:30",
  "timezone": "America/Chicago",
  "timezone_label": "CT",
  "alerts": { "ntfy_topic": "" },
  "dropbox": false,

  "page_url": "(filled in by setup)",
  "trigger_id": "(filled in by setup)"
}
```

- `newsletters`: read newsletters from Gmail. `outlook`: read newsletters from Outlook
  (Microsoft 365). Either, both or neither; missing means false.
- `newsletter_senders` (used for both Gmail and Outlook) empty means "find my
  newsletters automatically".
- `time` is when the brief should be ready; the Routine starts about 8 minutes earlier.
- `voice` is any Edge TTS voice name.
- `alerts.ntfy_topic`: optional; a long random name for the free ntfy app.
