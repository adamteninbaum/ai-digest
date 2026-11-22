"""Strip Apple News page clutter from a saved article's paragraphs.

The Mac capture of an Apple News article picks up more than the story: "Popular in News+"
carousels and ads at the bottom, newsletter sign-ups ("YES, SIGN ME UP!"), "Write to <author>
at <email>" lines, app promos, image placeholders, "Click for more" / "More Health News"
widgets, and scrambled fragments of pull quotes. clean() removes them so the page's full
text, the full-article audio, and the share PDF and text file only carry the article.

Used by saved.py (when articles come in) and share.py (when the share folder is built).
Usage for a quick check: python3 clean_article.py ARTICLE_JSON   (prints what it would drop)
"""
import json
import re
import sys

# Everything from the first of these to the end is page furniture, not the article.
# Only applied in the second half of the article, so a story that mentions them is safe.
CUT_FROM = [re.compile(p, re.I) for p in (
    r"^popular in news\+",
    r"^write to .{2,80} at \S+@\S+",
    r"^yes, sign me up",
    r"^(sign up|subscribe) (for|to) (our|the)\b",
    r"follow the journalists you trust",
    r"^download .{0,40}\bapp\b",
    r"^(more|top) stories\b",
    r"^(read|see) (more|next)\b:?$",
)]

# Dropped wherever they appear.
DROP = [re.compile(p, re.I) for p in (
    r"\bnews\+",                                   # Apple News+ chrome and carousels
    r"click for more\.?",
    r"more (health|news|business|tech) news\b",
    r"^\[image\b",
    r"follow us in apple news",
    r"^photo:",
    r"^(\d+[mhdw] ago\s*)+$",
    r"^advertisement$",
    r"^(share|save|listen|subscribe)( this (article|story))?$",
    r"get our daily newsletter",
)]

STOPWORD_END = re.compile(r"\b(to|of|the|and|a|an|for|with|in|on|at|by|from|or)$", re.I)
BIO = re.compile(r"^[A-Z][\w.'’-]+( [A-Z][\w.'’-]+){1,3} (is|was) (a|an|the|[A-Z][\w’']+)\b.*\b"
                 r"(reporter|writer|editor|correspondent|columnist|contributor|journalist)\b")


def clean(paras, title=""):
    """Return (kept, dropped) lists of paragraphs."""
    paras = [" ".join(p.split()) for p in paras if p and p.strip()]
    dropped = []
    # 1. Cut the trailing page furniture.
    half = len(paras) // 2
    for i, p in enumerate(paras):
        if i >= half and any(r.search(p) for r in CUT_FROM):
            dropped += paras[i:]
            paras = paras[:i]
            break
    kept, seen = [], set()
    t = (title or "").strip().lower()
    for p in paras:
        low = p.lower()
        words = p.split()
        junk = (any(r.search(p) for r in DROP)
                or low in seen
                or (t and low == t)
                # A short broken fragment such as "Who Is Most to": no end punctuation, ends on a stopword.
                or (len(words) <= 8 and p[-1:] not in ".!?\"'”’:" and STOPWORD_END.search(p)))
        if junk:
            dropped.append(p)
        else:
            kept.append(p)
            seen.add(low)
    # 2. A closing one-line author bio ("Jane Doe is The Post's tech reporter ...").
    if kept and len(kept[-1].split()) <= 40 and BIO.search(kept[-1]):
        dropped.append(kept.pop())
    return kept, dropped


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        doc = json.load(fh)
    kept, dropped = clean(doc.get("paragraphs") or [], doc.get("title", ""))
    print(f"keeps {len(kept)}, drops {len(dropped)}:")
    for p in dropped:
        print("  -", p[:140])
