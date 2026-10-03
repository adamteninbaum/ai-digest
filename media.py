"""Pull an interesting image or video for each digest item, so it shows on the page itself.

Usage: python3 media.py digest.json [OUT_DIR=media]
For every item, tries the item's "media_urls" first (direct image/video links or pages you
picked), then its "urls" in order, and stops at the first page that yields media. Writes the
files to OUT_DIR as <id>-<n>-<k>.jpg / .mp4, sets item["media"] in digest.json, and prints the
"files" entries to add to the Artifact publish.

item["media"] entries:
  {"type": "image", "src": "media/x.jpg", "w": 1200, "h": 675}
  {"type": "video", "src": "media/x.mp4", "poster": "media/x.jpg"}   playable on the page
  {"type": "link", "url": "https://youtube...", "poster": "media/x.jpg", "label": "Watch on YouTube"}
The page cannot embed other sites (no YouTube iframes), so YouTube and videos too large to
host become a poster image that opens the video.
Sources: X/Twitter posts (via api.fxtwitter.com), YouTube links, and any page's og:image /
og:video / twitter:image / <video> tags. Generic cards (GitHub, HN, logos, tiny images) are skipped.
"""
import io
import json
import os
import re
import sys
from html import unescape
from urllib.parse import urljoin, urlparse

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
CA = "/root/.ccr/ca-bundle.crt"
VERIFY = CA if os.path.exists(CA) else True
MAX_VIDEO = 14 * 1024 * 1024
MAX_IMAGE_W = 1200
SKIP_HOSTS = ("news.ycombinator.com", "opengraph.githubassets.com", "github.githubassets.com",
              "techmeme.com", "news.google.com")
SKIP_IMG = re.compile(r"(logo|favicon|avatar|sprite|placeholder|default[-_]?(og|share|social)|icon)", re.I)


def get(url, **kw):
    return requests.get(url, headers=UA, timeout=25, verify=VERIFY, **kw)


def yt_id(url):
    m = re.search(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else None


def x_status(url):
    m = re.search(r"(?:x|twitter)\.com/[^/]+/status/(\d+)", url)
    return m.group(1) if m else None


def meta(html, *names):
    for n in names:
        for pat in (rf'<meta[^>]+(?:property|name)=["\']{re.escape(n)}["\'][^>]*content=["\']([^"\']+)',
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{re.escape(n)}["\']'):
            m = re.search(pat, html, re.I)
            if m:
                return unescape(m.group(1)).strip()
    return ""


def candidates(url):
    """Return a list of (kind, media_url, extra) found for a page or direct link."""
    host = urlparse(url).netloc.lower()
    if any(h in host for h in SKIP_HOSTS):
        return []
    path = urlparse(url).path.lower()
    if re.search(r"\.(jpe?g|png|webp|gif)$", path):
        return [("image", url, {})]
    if path.endswith(".mp4"):
        return [("video", url, {})]
    vid = yt_id(url)
    if vid:
        return [("link", url, {"poster": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
                               "label": "Watch on YouTube"})]
    sid = x_status(url)
    if sid:
        try:
            t = get(f"https://api.fxtwitter.com/status/{sid}").json().get("tweet") or {}
        except Exception:
            return []
        out = []
        for v in (t.get("media") or {}).get("videos", []) or []:
            out.append(("video", v.get("url"), {"poster": v.get("thumbnail_url"), "page": url}))
        for p in (t.get("media") or {}).get("photos", []) or []:
            out.append(("image", p.get("url"), {}))
        return [o for o in out if o[1]]
    try:
        r = get(url)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return []
        html = r.text[:600000]
    except Exception:
        return []
    out = []
    v = meta(html, "og:video:secure_url", "og:video:url", "og:video", "twitter:player:stream")
    if v and (".mp4" in v.lower() or "video/mp4" in html.lower()):
        out.append(("video", urljoin(url, v), {"page": url}))
    m = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+\.mp4[^"\']*)', html, re.I)
    if m:
        out.append(("video", urljoin(url, unescape(m.group(1))), {"page": url}))
    m = re.search(r'(?:youtube\.com/embed/|youtube-nocookie\.com/embed/)([\w-]{11})', html)
    if m:
        out.append(("link", f"https://www.youtube.com/watch?v={m.group(1)}",
                    {"poster": f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg", "label": "Watch on YouTube"}))
    img = meta(html, "og:image:secure_url", "og:image", "twitter:image", "twitter:image:src")
    if img and not SKIP_IMG.search(img):
        out.append(("image", urljoin(url, img), {}))
    return out


def save_image(src, dest):
    from PIL import Image
    r = get(src)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    if im.width < 400 or im.height < 200:
        raise ValueError("too small")
    im = im.convert("RGB")
    if im.width > MAX_IMAGE_W:
        im = im.resize((MAX_IMAGE_W, round(im.height * MAX_IMAGE_W / im.width)), Image.LANCZOS)
    im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
    return im.width, im.height


def save_video(src, dest):
    with get(src, stream=True) as r:
        r.raise_for_status()
        size = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(256 * 1024):
                size += len(chunk)
                if size > MAX_VIDEO:
                    fh.close()
                    os.remove(dest)
                    raise ValueError("too big")
                fh.write(chunk)


def media_for(item, prefix, out_dir):
    """One piece of media per item: a playable video if there is one, else a video poster that
    opens it, else the best image. Tries each URL in order and stops at the first that works."""
    urls = list(item.get("media_urls") or [])
    urls += [u if isinstance(u, str) else u.get("url", "") for u in item.get("urls") or []]
    base = os.path.join(out_dir, prefix)
    for url in [u for u in urls if u]:
        try:
            cands = candidates(url)
        except Exception as e:
            print(f"  skip {url[:90]}: {type(e).__name__}", file=sys.stderr)
            continue
        cands.sort(key=lambda c: {"video": 0, "link": 1, "image": 2}[c[0]])
        for kind, src, extra in cands:
            try:
                if kind == "image":
                    w, h = save_image(src, base + ".jpg")
                    return [{"type": "image", "src": base + ".jpg", "w": w, "h": h}]
                poster = None
                if extra.get("poster"):
                    try:
                        save_image(extra["poster"], base + "-poster.jpg")
                        poster = base + "-poster.jpg"
                    except Exception:
                        pass
                if kind == "video":
                    try:
                        save_video(src, base + ".mp4")
                        return [{"type": "video", "src": base + ".mp4", "poster": poster}]
                    except Exception as e:
                        print(f"  video skipped ({e})", file=sys.stderr)
                if poster:
                    return [{"type": "link", "url": src if kind == "link" else (extra.get("page") or url),
                             "poster": poster, "label": extra.get("label", "Watch the video")}]
            except Exception as e:
                print(f"  skip {src[:90]}: {type(e).__name__}: {e}"[:160], file=sys.stderr)
    return []


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "media"
    os.makedirs(out_dir, exist_ok=True)
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    bid = d.get("id") or d.get("date", "brief")
    files = {}
    for n, item in enumerate(d.get("items", []), 1):
        if item.get("media") == []:
            continue  # explicitly turned off for this item
        found = media_for(item, f"{bid}-{n}", out_dir)
        item["media"] = found
        for f in found:
            for key in ("src", "poster"):
                if f.get(key):
                    files[f[key]] = f[key]
        print(f"item {n}: " + (", ".join(f["type"] for f in found) or "no media"), file=sys.stderr)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    print(json.dumps(files, indent=1))


if __name__ == "__main__":
    main()
