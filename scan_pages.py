#!/usr/bin/env python3
"""
Step 1: Scan all page images and identify which recipe (if any) is on each page.
Outputs: page_index.json — maps file_page_number → {recipe_title, is_continuation}
"""
import anthropic
import base64
import json
import os
import time

PAGES_DIR = "../pages"
OUTPUT_FILE = "./page_index.json"
MODEL = "claude-opus-4-6"

def load_image_b64(page_num):
    path = os.path.join(PAGES_DIR, f"page_{page_num:03d}.jpeg")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def identify_page(client, page_num):
    b64 = load_image_b64(page_num)
    if not b64:
        return None

    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": (
                    "Look at this cookbook page. Return ONLY valid JSON with these fields:\n"
                    '{"recipe_title": "exact title as printed, or null if no recipe (section divider/intro)", '
                    '"is_continuation": true/false (true if page says CONTINUACIÓN), '
                    '"printed_page": number shown at bottom of page}\n'
                    "No markdown, no explanation — just the JSON."
                )}
            ]
        }]
    )
    import re
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()
    return json.loads(raw)

def main():
    client = anthropic.Anthropic()

    index = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            index = json.load(f)
        print(f"Resuming — {len(index)} pages already scanned")

    total = 204
    for page_num in range(1, total + 1):
        key = str(page_num)
        if key in index:
            continue

        print(f"[{page_num:3d}/204] scanning...", end="", flush=True)
        try:
            result = identify_page(client, page_num)
            index[key] = result
            title = result.get("recipe_title", "—") if result else "—"
            print(f" {title[:60]}")
        except Exception as e:
            print(f" ERROR: {e}")
            index[key] = None
            time.sleep(2)

        if page_num % 10 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            print(f"  → checkpoint saved")
        time.sleep(0.5)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\nDone! page_index.json written.")

if __name__ == "__main__":
    main()
