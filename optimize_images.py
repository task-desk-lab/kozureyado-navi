#!/usr/bin/env python3
"""Backfill image perf for existing hotel pages.

For each content/hotels/<no>/index.md:
  1. Resize local theme JPEGs (meal_/bath_/area_*) in place to <=720px, q72.
  2. Rewrite the Rakuten hero from the full `share/HOTEL/<no>/<no>.jpg`
     (up to 2MB) to the `HIMG/300/<no>.jpg` thumbnail (~20KB).
  3. Add explicit width/height to every <img> so CLS goes to ~0.

Idempotent: skips already-small images and imgs that already have width=.
"""
import re
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).parent
HOTELS = ROOT / "content" / "hotels"
MAX_W = 720
Q = 72

hero_share = re.compile(
    r"(https://img\.travel\.rakuten\.co\.jp/)share/HOTEL/(\d+)/\2\.jpg"
)


def resize_local(p: Path) -> tuple[int, int]:
    """Resize a local JPEG in place (if large). Return final (w, h)."""
    with Image.open(p) as im:
        w, h = im.size
        if w > MAX_W:
            nh = round(h * MAX_W / w)
            im = im.convert("RGB").resize((MAX_W, nh), Image.LANCZOS)
            im.save(p, "JPEG", quality=Q, optimize=True, progressive=True)
            return MAX_W, nh
        return w, h


def add_dims(tag: str, w: int, h: int) -> str:
    """Insert width/height into an <img ...> tag if absent."""
    if "width=" in tag:
        return tag
    return tag.replace("<img ", f'<img width="{w}" height="{h}" ', 1)


def process(md: Path) -> bool:
    hotel_dir = md.parent
    text = md.read_text()
    orig = text

    # 1. hero: share -> HIMG/300, dims 300x169
    text = hero_share.sub(r"\1HIMG/300/\2.jpg", text)

    # 2. walk every <img ...> and size it
    def repl(m: re.Match) -> str:
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if not src:
            return tag
        s = src.group(1)
        if "HIMG/300" in s:
            return add_dims(tag, 300, 169)
        if s.startswith("http"):
            return tag  # other remote image, leave as-is
        # local theme image — resize file, then size the tag
        f = hotel_dir / s
        if f.exists():
            w, h = resize_local(f)
            return add_dims(tag, w, h)
        return tag

    text = re.sub(r"<img [^>]*>", repl, text)

    if text != orig:
        md.write_text(text)
        return True
    return False


def main():
    mds = sorted(HOTELS.glob("*/index.md"))
    changed = 0
    for md in mds:
        if process(md):
            changed += 1
    print(f"processed {len(mds)} hotel pages, modified {changed}")


if __name__ == "__main__":
    main()
