"""Keep the digest page under its storage cap by dropping old video copies.

The page holds at most 256 MiB of files. Videos are the biggest part, and they are copies of
public clips (each story still links to the original), so videos from briefs older than
KEEP_DAYS are removed. The page hides a video whose file is gone.

Usage: python3 prune_media.py LISTING_TXT [KEEP_DAYS=21]
  LISTING_TXT: the Artifact `list` (scope files) output for the page, saved as text.
Prints the total size, then the JSON map of files to remove ({"media/x.mp4": null, ...}) as
its LAST line; merge it into the next publish's `files`. Prints {} when nothing is due.
"""
import json
import re
import sys
from datetime import date, timedelta

CAP = 256 * 1024 * 1024
LINE = re.compile(r'"([^"]+)"\s+\S+\s+(\d+) bytes')
VIDEO = re.compile(r"^media/(\d{4}-\d{2}-\d{2})[^/]*\.mp4$")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 21
    cutoff = (date.today() - timedelta(days=keep)).isoformat()
    files = [(m.group(1), int(m.group(2))) for m in LINE.finditer(open(sys.argv[1], encoding="utf-8").read())]
    total = sum(s for _, s in files)
    drop = {p: s for p, s in files if (v := VIDEO.match(p)) and v.group(1) < cutoff}
    freed = sum(drop.values())
    mib = lambda b: f"{b / 1048576:.1f} MiB"
    print(f"page files: {len(files)}, {mib(total)} of {mib(CAP)}; dropping {len(drop)} videos older than "
          f"{keep} days ({mib(freed)}) -> {mib(total - freed)}")
    if total - freed > CAP * 0.85:
        print("WARNING: still over 85% of the cap after pruning; say so in the step 9 summary")
    print(json.dumps({p: None for p in sorted(drop)}))


if __name__ == "__main__":
    main()
