#!/usr/bin/env python3
"""
crop_photos.py — Crop food photos from Mesa Sana recipe pages.

Each page has the food photo on the LEFT side (~0-44% of width, top ~80% height).
Reads from pages/ folder, outputs to photos/ folder + photo_map.json.
"""

import os
import json
import re
import unicodedata
from PIL import Image

PAGES_DIR = "./pages"
PHOTOS_DIR = "./photos"

# Crop box as fractions of image dimensions (left, upper, right, lower)
CROP_LEFT   = 0.0
CROP_TOP    = 0.0
CROP_RIGHT  = 0.44
CROP_BOTTOM = 0.82


def slugify(text):
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text


def crop_photo(img_path, out_path):
    with Image.open(img_path) as img:
        w, h = img.size
        box = (
            int(w * CROP_LEFT),
            int(h * CROP_TOP),
            int(w * CROP_RIGHT),
            int(h * CROP_BOTTOM),
        )
        cropped = img.crop(box)
        cropped.save(out_path, "JPEG", quality=90)


def main():
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    # Load page index to get recipe titles per page
    photo_map = {}  # recipe_key -> photo filename

    if os.path.exists("page_index.json"):
        with open("page_index.json") as f:
            index = json.load(f)
    else:
        index = {}

    pages = sorted(
        [f for f in os.listdir(PAGES_DIR) if f.endswith(".jpeg") or f.endswith(".jpg")],
        key=lambda x: int(re.search(r'\d+', x).group())
    )

    print(f"Found {len(pages)} pages to process")

    for filename in pages:
        page_num = int(re.search(r'\d+', filename).group())
        img_path = os.path.join(PAGES_DIR, filename)

        info = index.get(str(page_num))
        title = info.get("recipe_title") if info else None
        is_continuation = info.get("is_continuation", False) if info else False

        if not title:
            out_name = f"page_{page_num:03d}.jpg"
        else:
            slug = slugify(title)
            suffix = f"-cont" if is_continuation else ""
            out_name = f"{slug}{suffix}.jpg"

        out_path = os.path.join(PHOTOS_DIR, out_name)
        crop_photo(img_path, out_path)

        if title and not is_continuation:
            photo_map[title] = out_name

        print(f"  [{page_num:03d}] {out_name}")

    # Save photo map
    map_path = os.path.join(PHOTOS_DIR, "photo_map.json")
    with open(map_path, "w") as f:
        json.dump(photo_map, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(pages)} photos saved to {PHOTOS_DIR}/")
    print(f"photo_map.json written with {len(photo_map)} recipe entries")


if __name__ == "__main__":
    main()
