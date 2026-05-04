#!/usr/bin/env python3
"""
Repair script: re-extracts all broken recipes using correct file pages from page_index.json,
fixes names to Title Case, and adds image references.
"""
import anthropic
import base64
import json
import os
import re
import time
import unicodedata

PAGES_DIR = "../pages"
INDEX_FILE = "./page_index.json"
RECIPES_FILE = "./recipes_bilingual.json"
MODEL = "claude-opus-4-6"
MAX_TOKENS = 2500

SYSTEM_PROMPT = """You are extracting recipe data from Mexican cookbook pages for a bilingual wellness app.

Extract EXACTLY what is on the page — do not invent, summarize, or paraphrase.
Return ONLY valid JSON matching this schema exactly — no markdown, no extra text.

SCHEMA:
{
  "name_es": "exact Spanish name as printed (Title Case, not ALL CAPS)",
  "name_en": "accurate English translation of the name",
  "servings": "number as string e.g. '4'",
  "phases": [1] or [2] or [1,2] or [3] — only phases shown in the fase boxes,
  "equiv": {
    "protein": "0", "veggie": "0", "carb": "0", "fat": "0", "fruit": "0"
  },
  "equiv_note_es": "e.g. 'por 1 porción' or 'por 2 enchiladas' — exact text from page",
  "equiv_note_en": "English translation of equiv_note_es",
  "equiv_modifier_es": "optional text like 'Con 2 cdas crema y queso: +1 Grasa' or null",
  "equiv_modifier_en": "English translation of equiv_modifier or null",
  "ingredients_es": [
    {
      "label": null or "PARA LA SALSA" — exact label from page, null if no label,
      "items": ["exact ingredient text", ...]
    }
  ],
  "ingredients_en": [
    {
      "label": null or "FOR THE SAUCE" — translated label,
      "items": ["translated ingredient", ...]
    }
  ],
  "tip_es": "text of any * tip note or null",
  "tip_en": "English translation of tip or null",
  "instructions_es": [
    {
      "label": null or "PARA LA SALSA" — subsection label if present,
      "steps": ["step 1 text", "step 2 text", ...]
    }
  ],
  "instructions_en": [
    {
      "label": null or "FOR THE SAUCE",
      "steps": ["step 1 translated", ...]
    }
  ]
}

RULES:
- name_es: use Title Case (e.g. "Enchiladas de Jamaica y Panela con Salsa Morita"), never ALL CAPS
- equiv values: use strings like "0", "1", "1/2", "1.5"
- ingredients_es/en: always an array even if only one group (with label: null)
- instructions_es/en: always an array even if only one group (with label: null)
- If a page says CONTINUACIÓN it is the continuation of a multi-page recipe — extract all content across all provided pages as one recipe
- Translate ingredient terms: jitomate→tomato, cebolla→onion, aguacate→avocado, poro→leek, elote→corn, cda→tbsp, cdita→tsp, taza→cup, nopal→cactus paddle, jocoque→sour cream, queso panela→panela cheese, queso de cabra→goat cheese, champiñón→mushroom, calabaza/calabacita→zucchini, jitomate saladet→roma tomato, chile serrano→serrano pepper, chile chipotle→chipotle pepper
- Translate section headers: INGREDIENTES→INGREDIENTS, PROCEDIMIENTO→INSTRUCTIONS, PARA LA SALSA→FOR THE SAUCE, PARA EL→FOR THE, PARA SERVIR→TO SERVE, PARA DECORAR→TO GARNISH, PARA LA VINAGRETA→FOR THE DRESSING, PARA EL ADEREZO→FOR THE DRESSING
"""

def normalize(s):
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', ' ', s).strip()

def title_case(s):
    minor = {'de','del','y','con','en','el','la','los','las','un','una','o','a','sin','al','por','sobre','que'}
    words = s.split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in minor:
            result.append(w.capitalize())
        else:
            result.append(w.lower())
    return ' '.join(result)

def load_image_b64(page_num):
    path = os.path.join(PAGES_DIR, f"page_{page_num:03d}.jpeg")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def extract_recipe(client, name, file_pages):
    content = []
    for p in file_pages:
        b64 = load_image_b64(p)
        if b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    content.append({"type": "text", "text": f'Extract the recipe "{name}" from the provided page image(s). Return only the JSON.'})

    resp = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}])
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()
    return json.loads(raw)

def build_index_map():
    with open(INDEX_FILE) as f:
        index = json.load(f)
    # recipe_title -> list of file page numbers
    from collections import defaultdict
    mapping = defaultdict(list)
    for file_num_str, info in sorted(index.items(), key=lambda x: int(x[0])):
        if not info:
            continue
        title = info.get('recipe_title')
        if title:
            mapping[normalize(title)].append(int(file_num_str))
    return dict(mapping)

def find_pages(index_map, recipe_name):
    key = normalize(recipe_name)
    if key in index_map:
        return index_map[key]
    # fuzzy: find best partial match
    best, best_score = None, 0
    for idx_key, pages in index_map.items():
        common = sum(1 for w in key.split() if w in idx_key.split() and len(w) > 3)
        if common > best_score:
            best_score = common
            best = pages
    return best if best_score >= 2 else None

def main():
    client = anthropic.Anthropic()
    index_map = build_index_map()

    with open(RECIPES_FILE) as f:
        recipes = json.load(f)

    # Identify broken recipes
    broken = []
    for key, v in recipes.items():
        ing = sum(len(g.get('items', [])) for g in v.get('ingredients_es', []))
        inst = sum(len(g.get('steps', [])) for g in v.get('instructions_es', []))
        if ing == 0 or inst == 0:
            broken.append(key)

    # Also add failed recipes (not in JSON at all)
    failed = [
        "POLLO O PESCADO PIBIL CON CEBOLLITA ENCURTIDA",
        "SALMÓN AL CHIPOTLE CON ENSALADA DE LENTEJA",
        "EJOTES CON ALMENDRAS",
        "PAPITAS CON ORÉGANO",
        "MUFFINS DE BLUEBERRY SIN HARINA",
        "SORBETE DE FRESA",
    ]
    to_fix = list(dict.fromkeys(broken + [f for f in failed if f not in recipes]))

    print(f"Recipes to fix: {len(to_fix)}")
    errors = []

    for i, name in enumerate(to_fix):
        pages = find_pages(index_map, name)
        if not pages:
            print(f"[{i+1}/{len(to_fix)}] {name[:50]} — NO PAGES FOUND, skipping")
            errors.append(name)
            continue

        print(f"[{i+1}/{len(to_fix)}] {name[:50]:<50} pages={pages}...", end="", flush=True)
        try:
            data = extract_recipe(client, name, pages)
            # Fix name_es casing
            data['name_es'] = title_case(data.get('name_es', name))
            data['name_en'] = data.get('name_en', '')
            data['images'] = [f"page_{p:03d}.jpeg" for p in pages]
            recipes[name] = data
            print(" ✓")
        except Exception as e:
            print(f" ✗ {e}")
            errors.append(name)
            time.sleep(2)
            continue

        time.sleep(0.8)

    # Fix Title Case and add images for ALL recipes
    print("\nFixing names and adding images for all recipes...")
    for key, v in recipes.items():
        if 'name_es' in v:
            v['name_es'] = title_case(v['name_es'])
        if 'images' not in v:
            # Try to find images from index
            pages = find_pages(index_map, key)
            if pages:
                v['images'] = [f"page_{p:03d}.jpeg" for p in pages]

    with open(RECIPES_FILE, "w") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(recipes)} recipes saved.")
    if errors:
        print(f"Still failed ({len(errors)}): {', '.join(errors)}")

if __name__ == "__main__":
    main()
