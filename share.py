"""Friends-and-family links for saved articles: the "Share with friends & family" button.

For every saved-article item in a brief, makes a Dropbox folder
/Claude/news-capture/shared/<date> <title>/ holding the article as a PDF (title, byline,
lead image when the article page has one, full text), a plain text copy, and its full audio
as an MP3, makes a
public view-only link to the folder, and stores it on the item as item["full"]["share"].
The page turns that into the share button (phone share sheet, else copy the link).

Usage:
  python3 share.py [--all] BRIEF_JSON [FULL_DIR] [AUDIO_ROOT]
    BRIEF_JSON  the brief to update in place (e.g. out/briefs/<id>.json)
    FULL_DIR    folder with the full-article JSONs (default: out/briefs/full)
    AUDIO_ROOT  folder the versions' "src" paths are relative to, used when the MP3 is not in
                ./audio_full/ where saved.py render leaves it (default: current folder)
Items that already have a share link are skipped, so it is safe to run again; with --all
they are rebuilt too (files overwritten, the folder's existing link reused).
Prints one line per article and "shared N" at the end. Exit code 1 if any article failed.

Needs DROPBOX_APP_KEY / _SECRET / _REFRESH_TOKEN (the same keys saved.py uses) with scopes
files.content.write and sharing.write.
"""
import io
import json
import os
import re
import sys
import unicodedata
from html import unescape

import requests

from clean_article import clean
from saved import VERIFY, token

SHARED = "/Claude/news-capture/shared"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"}


def safe_name(title):
    t = re.sub(r"\s*[\u2013\u2014]\s*", " ", title)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[\\/:*?\"<>|'’‘“”]", "", t)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t[:90] or "Article"


def lead_image(link):
    """The article's og:image from its Apple News page, as JPEG bytes, or None."""
    if not link:
        return None
    try:
        html = requests.get(link, headers=UA, timeout=20, verify=VERIFY).text[:400000]
        m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
             or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html, re.I))
        if not m:
            return None
        from PIL import Image
        img = Image.open(io.BytesIO(requests.get(unescape(m.group(1)), headers=UA, timeout=20, verify=VERIFY).content))
        if img.width < 400:
            return None
        img = img.convert("RGB")
        if img.width > 1400:
            img = img.resize((1400, round(img.height * 1400 / img.width)))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=85)
        return out.getvalue()
    except Exception:
        return None


def clean_paragraphs(doc):
    paras = list(doc.get("paragraphs") or [])
    # The first spoken paragraph repeats the title and byline ("<Title>. From <Source>, by ...").
    if paras and doc.get("title") and paras[0].startswith(doc["title"][:40]):
        paras = paras[1:]
    # Leftovers from the Apple News capture (ads, sign-ups, widgets): see clean_article.py.
    return clean(paras, doc.get("title") or "")[0]


def byline(doc):
    return " · ".join(x for x in (doc.get("source"), doc.get("author") and "by " + doc["author"], doc.get("date")) if x)


def make_txt(doc):
    head = [doc.get("title") or "Article", byline(doc), doc.get("link") or ""]
    return ("\n".join(h for h in head if h) + "\n\n" + "\n\n".join(clean_paragraphs(doc)) + "\n").encode("utf-8")


def make_pdf(doc, path):
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Title"], fontName="Times-Bold", fontSize=22, leading=27, alignment=TA_LEFT)
    meta = ParagraphStyle("m", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor="#555555")
    body = ParagraphStyle("b", parent=ss["Normal"], fontName="Times-Roman", fontSize=11.5, leading=16.5, spaceAfter=8)
    flow = [Paragraph(esc(doc.get("title")), title), Spacer(1, 4)]
    by = byline(doc)
    if by:
        flow.append(Paragraph(esc(by), meta))
    if doc.get("link"):
        flow.append(Paragraph('<link href="%s">%s</link>' % (esc(doc["link"]), esc(doc["link"])), meta))
    flow.append(Spacer(1, 14))
    jpg = lead_image(doc.get("link"))
    if jpg:
        img = Image(io.BytesIO(jpg))
        w = 6.5 * inch
        img.drawHeight, img.drawWidth = img.imageHeight * w / img.imageWidth, w
        if img.drawHeight > 4.5 * inch:
            img.drawWidth, img.drawHeight = img.drawWidth * 4.5 * inch / img.drawHeight, 4.5 * inch
        flow += [img, Spacer(1, 14)]
    flow += [Paragraph(esc(p), body) for p in clean_paragraphs(doc)]
    SimpleDocTemplate(path, pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch,
                      bottomMargin=0.9 * inch, title=doc.get("title") or "Article",
                      author=doc.get("author") or "").build(flow)
    return bool(jpg)


def upload(tok, data, remote):
    r = requests.post("https://content.dropboxapi.com/2/files/upload", timeout=300, verify=VERIFY, data=data,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/octet-stream",
                               "Dropbox-API-Arg": json.dumps({"path": remote, "mode": "overwrite", "mute": True})})
    if not r.ok:
        raise RuntimeError(f"upload {remote}: {r.status_code} {r.text[:200]}")


def public_link(tok, path):
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    r = requests.post("https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings", headers=h,
                      timeout=30, verify=VERIFY,
                      json={"path": path, "settings": {"requested_visibility": "public", "access": "viewer"}})
    if r.ok:
        return r.json()["url"]
    if "shared_link_already_exists" in r.text:
        r2 = requests.post("https://api.dropboxapi.com/2/sharing/list_shared_links", headers=h, timeout=30,
                           verify=VERIFY, json={"path": path, "direct_only": True})
        if r2.ok and r2.json().get("links"):
            return r2.json()["links"][0]["url"]
    raise RuntimeError(f"link {path}: {r.status_code} {r.text[:200]}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    redo = "--all" in sys.argv
    sys.argv = [a for a in sys.argv if a != "--all"]
    brief_path = sys.argv[1]
    full_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join("out", "briefs", "full")
    audio_root = sys.argv[3] if len(sys.argv) > 3 else "."
    with open(brief_path, encoding="utf-8") as fh:
        brief = json.load(fh)
    todo = [it for it in brief.get("items", []) if it.get("saved") and it.get("full") and (redo or not it["full"].get("share"))]
    if not todo:
        print("shared 0 (no saved articles without a link)")
        return
    tok = token()
    done, failed = 0, 0
    os.makedirs("share_out", exist_ok=True)
    for it in todo:
        key = it["saved"]
        try:
            with open(os.path.join(full_dir, key + ".json"), encoding="utf-8") as fh:
                doc = json.load(fh)
            name = safe_name(doc.get("title") or it.get("title") or key)
            folder = f"{SHARED}/{brief.get('date', '')} {name}".replace("  ", " ")
            pdf = os.path.join("share_out", key + ".pdf")
            had_img = make_pdf(doc, pdf)
            with open(pdf, "rb") as fh:
                upload(tok, fh.read(), f"{folder}/{name}.pdf")
            upload(tok, make_txt(doc), f"{folder}/{name} (text).txt")
            mp3 = next((v["src"] for v in doc.get("versions", []) if v.get("src") and not v.get("sample")), None)
            # saved.py render keeps the MP3 locally in audio_full/; a page copy lives under audio/.
            cands = [os.path.join("audio_full", os.path.basename(mp3)), os.path.join(audio_root, mp3)] if mp3 else []
            mp3_path = next((c for c in cands if os.path.exists(c)), None)
            if mp3_path and os.path.exists(mp3_path):
                with open(mp3_path, "rb") as fh:
                    upload(tok, fh.read(), f"{folder}/{name} (audio).mp3")
            it["full"]["share"] = public_link(tok, folder)
            done += 1
            print(f"{key}: {folder} ({'with' if had_img else 'no'} image, "
                  f"{'with' if mp3_path and os.path.exists(mp3_path) else 'no'} audio)")
        except Exception as e:
            failed += 1
            print(f"{key}: FAILED {type(e).__name__}: {str(e)[:200]}")
    with open(brief_path, "w", encoding="utf-8") as fh:
        json.dump(brief, fh, ensure_ascii=False, indent=1)
    print(f"shared {done}" + (f", failed {failed}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
