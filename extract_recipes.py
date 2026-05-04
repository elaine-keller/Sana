#!/usr/bin/env python3
"""
Mesa Sana — Bilingual Recipe Extractor
Reads each recipe page image visually and extracts structured bilingual data.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 extract_recipes.py

Expects a pages/ folder in the same directory containing page_001.jpeg ... page_204.jpeg
Outputs: recipes_bilingual.json
"""

import anthropic
import json
import base64
import os
import time
import re

# ── CONFIG ──────────────────────────────────────────────────────────────────
PAGES_DIR = "./pages"
OUTPUT_FILE = "./recipes_bilingual.json"
CHECKPOINT_EVERY = 5   # save progress every N recipes
MODEL = "claude-opus-4-6"
MAX_TOKENS = 2500
SLEEP_BETWEEN = 0.8    # seconds between API calls
# ────────────────────────────────────────────────────────────────────────────

RECIPES_WITH_PAGES = [
    {"name": "ENCHILADAS HEALTHY DE CALABAZA", "pages": [11, 12]},
    {"name": "FRITTATA DE SALMÓN AHUMADO CON ESPÁRRAGOS", "pages": [13, 14]},
    {"name": "HUEVOS AHOGADOS EN SALSA ROJA CON POBLANO", "pages": [15]},
    {"name": "HUEVOS ESTRELLADOS SOBRE VERDURAS", "pages": [16]},
    {"name": "SMOOTHIE COMPLETO", "pages": [17]},
    {"name": "HUEVO REVUELTO CON VERDURAS", "pages": [18]},
    {"name": "ROLLITOS DE PAVO CON VERDURAS", "pages": [19]},
    {"name": "SOPES DE NOPAL CON POLLO", "pages": [20]},
    {"name": "CARPACCIO DE SALMÓN AHUMADO", "pages": [21]},
    {"name": "HUEVO A LA MEXICANA CON PAVO", "pages": [22]},
    {"name": "CALABAZAS A LA MEXICANA CON POLLO O PAVO", "pages": [23]},
    {"name": "HUEVOS ESTRELLADOS CON SALSA ROJA", "pages": [24]},
    {"name": "OMELETTE RELLENO DE VERDURAS", "pages": [25]},
    {"name": "HUEVO SOBRE CHAMPIÑONES Y QUESO DE CABRA", "pages": [26]},
    {"name": "TOAST DE RAJAS POBLANAS, FLOR DE CALABAZA, PANELA Y HUEVO", "pages": [27]},
    {"name": "AVOCADO TOAST CON SALMÓN MARINADO", "pages": [28]},
    {"name": "TOAST DE JOCOQUE CON HUEVOS VERDES CON ESPÁRRAGOS Y HIERBAS", "pages": [29]},
    {"name": "CAZUELITA DE VERDURAS, PAVO Y FETA", "pages": [30]},
    {"name": "ENCHILADAS DE JAMAICA Y PANELA CON SALSA MORITA", "pages": [31, 32]},
    {"name": "SMOOTHIE LIGERO", "pages": [33]},
    {"name": "FRAPPÉ DE CAFÉ", "pages": [34]},
    {"name": "WAFFLES ALTOS EN PROTEÍNA CON QUESO COTTAGE", "pages": [35]},
    {"name": "TOAST DE HONGOS CON RICOTTA", "pages": [36]},
    {"name": "AVENA QUE NO SUBE LA GLUCOSA (OVERNIGHT OATS)", "pages": [37]},
    {"name": "PAN DE SEMILLAS SIN HARINA Y SIN LÁCTEOS", "pages": [38]},
    {"name": "SHAKSHUKA", "pages": [39]},
    {"name": "ENCHILADAS KETO CON SALSA DE TOMATE Y CHIPOTLE", "pages": [40]},
    {"name": "WAFFLES O HOT CAKES KETO", "pages": [41]},
    {"name": "SOPA DE BRÓCOLI (O CUALQUIER VERDURA) SIN CREMA", "pages": [44]},
    {"name": "SOPA DE VERDURA RALLADA", "pages": [45]},
    {"name": "SOPA DE APIO CON LIMÓN", "pages": [46]},
    {"name": "SOPA DE BRÓCOLI ROSTIZADO (CON O SIN QUESO)", "pages": [47]},
    {"name": "GAZPACHO", "pages": [48]},
    {"name": "SOPA DETOX", "pages": [49]},
    {"name": "SOPA DE TORTILLA CON POLLO", "pages": [50]},
    {"name": "SOPA DE RAJAS POBLANAS", "pages": [51]},
    {"name": "SOPA VERDE CON CALABAZA VERDOLAGA Y TOMATE VERDE", "pages": [52]},
    {"name": "SOPA DE FRIJOL CON CAMARÓN SERRANO Y QUESO (OPCIONAL)", "pages": [53]},
    {"name": "SOPA DE LA MILPA CON FLOR DE CALABAZA", "pages": [54]},
    {"name": "PUCHERO VERDE CON POBLANO Y CILANTRO", "pages": [55]},
    {"name": "SOPA DE HONGOS CON CHIPOTLE", "pages": [56]},
    {"name": "SOPA FRÍA DE PALMITO CON ALMENDRA TOSTADA", "pages": [57]},
    {"name": "SOPA DE ESPÁRRAGOS CON CALABAZA", "pages": [58]},
    {"name": "SOPA DE ZANAHORIA CON JENGIBRE", "pages": [59]},
    {"name": "SOPA DE ALCACHOFA Y PORO", "pages": [60]},
    {"name": "SOPA DE NOPALITOS", "pages": [61]},
    {"name": "CHICHARRÓN DE POLLO SIN ACEITE", "pages": [64]},
    {"name": "POLLO MARINADO EN YOGURT", "pages": [65]},
    {"name": "POLLO AL ORÉGANO, MOSTAZA Y LIMÓN", "pages": [66]},
    {"name": "POLLO A LA MOSTAZA", "pages": [67]},
    {"name": "POLLO AL ROMERO SOBRE PAPAS AL HORNO", "pages": [68]},
    {"name": "BROCHETAS DE POLLO CON SALSA DE CILANTRO Y AGUACATE", "pages": [69]},
    {"name": "POLLO O PESCADO PIBIL CON CEBOLLITA ENCURTIDA", "pages": [70, 71]},
    {"name": "SALMÓN AL CHIPOTLE CON ENSALADA DE LENTEJA", "pages": [72, 73]},
    {"name": "SALMÓN CON MOSTAZA Y TAJÍN", "pages": [74]},
    {"name": "SALMÓN CON SOYA, JENGIBRE Y LIMÓN", "pages": [75]},
    {"name": "SALMÓN CON SALSA DE PIMIENTA VERDE", "pages": [76]},
    {"name": "SALMÓN CON MOSTAZA, MIEL Y CHIPOTLE", "pages": [77]},
    {"name": "SALMÓN CON ZA'ATAR SOBRE ORZO CON CALABACITA Y ESPÁRRAGOS", "pages": [78]},
    {"name": "SALMÓN CON ENELDO Y LIMÓN", "pages": [79]},
    {"name": "FILETE CON ROMERO, BALSÁMICO Y MOSTAZA", "pages": [80]},
    {"name": "CEVICHE DE CECINA", "pages": [81]},
    {"name": "SALPICÓN DE RES", "pages": [82]},
    {"name": "ARRACHERA CON SALSA DE JITOMATE, AGUACATE Y HIERBAS", "pages": [83]},
    {"name": "BOWLS DE RIB EYE, POLLO O SALMÓN TERIYAKI", "pages": [84]},
    {"name": "PESCADO A LA PARRILLA CON SALSA DE ALCAPARRA Y PEREJIL", "pages": [85]},
    {"name": "PESCADO A LA PARRILLA CON HIERBAS SOBRE JITOMATE", "pages": [86]},
    {"name": "PESCADO AL CILANTRO", "pages": [87]},
    {"name": "SALPICÓN DE PESCADO ORIENTAL CON CHAMPIÑONES Y ESPÁRRAGOS", "pages": [88]},
    {"name": "SALPICÓN DE PESCADO CON AGUACATE Y SERRANO", "pages": [89]},
    {"name": "CAMARONES A LA PARRILLA CON CHILE GUAJILLO Y LIMÓN", "pages": [90]},
    {"name": "TACOS DE CAMARÓN CON PORO, CHILITO, CILANTRO Y LIMÓN", "pages": [91]},
    {"name": "TACOS DE CAMARÓN CON CHIPOTLE (SIN FRIJOLES)", "pages": [92]},
    {"name": "CARNITAS DE ATÚN SIN ACEITE", "pages": [93]},
    {"name": "CEVICHE DE ATÚN ORIENTAL", "pages": [94]},
    {"name": "ATÚN SELLADO CON EVERYTHING BUT THE BAGEL", "pages": [95]},
    {"name": "TACOS VIETNAMITAS DE LECHUGA CON SALSA DE CACAHUATE", "pages": [96]},
    {"name": "TACOS CHINOS DE POLLO EN HOJAS DE LECHUGA", "pages": [97]},
    {"name": "NOODLES DE CALABAZA CON BOLOGNESA", "pages": [98]},
    {"name": "POLLO A LAS HIERBAS SOBRE ZUCCHINI NOODLES CON PESTO", "pages": [99]},
    {"name": "PIZZAS DE PORTOBELLO CON AGUACATE Y SALMÓN", "pages": [100]},
    {"name": "ENSALADA DE TORONJA CON AGUACATE, PEPITA Y VINAGRETA DE MOSTAZA", "pages": [103]},
    {"name": "ENSALADA DE BERROS", "pages": [104]},
    {"name": "ENSALADA DE PEPINO Y EDAMAME", "pages": [105]},
    {"name": "ENSALADA DE ATÚN BONITO CON GARBANZO Y AGUACATE", "pages": [106]},
    {"name": "ENSALADA DE VERDOLAGAS Y NOPALES", "pages": [107]},
    {"name": "CARPACCIO DE JITOMATE CON QUESO OAXACA", "pages": [108]},
    {"name": "ENSALADA DE LISTONES DE CALABACITA Y BURRATA", "pages": [109]},
    {"name": "ENSALADA ISRAELÍ CON VINAGRETA DE ZA'ATAR", "pages": [110]},
    {"name": "LECHUGAS AL GRILL CON VINAGRETA DE CORAZONES", "pages": [111]},
    {"name": "CARPACCIO DE PORTOBELLO CON ARÚGULA Y NUEZ DE LA INDIA", "pages": [112]},
    {"name": "ENSALADA DE ELOTITOS CON JITOMATE", "pages": [113]},
    {"name": "ENSALADA THAI SIN CACAHUATE", "pages": [114]},
    {"name": "ENSALADA DE APIO CON PARMESANO", "pages": [115]},
    {"name": "ENSALADA MIXTA", "pages": [116]},
    {"name": "ENSALADA THAI CRUNCHY", "pages": [117]},
    {"name": "ENSALADA OTOÑAL", "pages": [118]},
    {"name": "ENSALADA DE ARÚGULA CON PERA, PARMESANO Y AJONJOLÍ GARAPIÑADO", "pages": [119]},
    {"name": "ENSALADA DE GARBANZO CON ALCACHOFA, ACEITUNA Y QUESO FETA", "pages": [120]},
    {"name": "ENSALADA DE PEPINO CON QUESO FETA Y HIERBAS FRESCAS", "pages": [121]},
    {"name": "ENSALADA DE PALMITOS CON ARÚGULA, JITOMATE CHERRY Y AGUACATE", "pages": [122]},
    {"name": "ENSALADA DE ATÚN SELLADO CON MANGO, AGUACATE Y EDAMAME", "pages": [123]},
    {"name": "TABULE A NUESTRO ESTILO", "pages": [124]},
    {"name": "CARPACCIO DE AGUACATE CON ENSALADA DE HIERBAS", "pages": [125]},
    {"name": "ENSALADA DE BETABEL CON ADEREZO DE TAHINI Y ENELDO", "pages": [126]},
    {"name": "ENSALADA DE JITOMATE CON ATÚN BONITO", "pages": [127]},
    {"name": "ENSALADA ORIENTAL DE POLLO, EDAMAME, PEPINO Y ZANAHORIA", "pages": [128]},
    {"name": "ESQUITES DE COLIFLOR", "pages": [131]},
    {"name": "PORTOBELLOS AL GRILL RELLENOS DE ALCACHOFA Y PEREJIL", "pages": [132]},
    {"name": "AGUACHILE DE PALMITO Y CHAMPIÑÓN", "pages": [133]},
    {"name": "CARPACCIO DE SALMÓN AHUMADO", "pages": [134]},
    {"name": "TIRADITO DE CAMARÓN CON SALSA TATEMADA", "pages": [135]},
    {"name": "AGUACHILE ROJO DE CAMARÓN", "pages": [136]},
    {"name": "CEVICHE DE PALMITO Y CORAZONES DE ALCACHOFA", "pages": [137]},
    {"name": "COGOLLOS CON BONITO Y PARMESANO", "pages": [138]},
    {"name": "TACOS VIETNAMITAS DE LECHUGA CON SALSA DE CACAHUATE", "pages": [139]},
    {"name": "AGUACHILE VERDE DE CAMARÓN", "pages": [140]},
    {"name": "CEVICHE DE PALMITO CON MANZANA", "pages": [141]},
    {"name": "CEVICHE PERUANO CON TOMATE Y MANGO", "pages": [142]},
    {"name": "CEVICHE DE PESCADO CON PEPINO Y HABANERO", "pages": [143]},
    {"name": "CEVICHE DE CAMARÓN ESTILO NAYARIT (TOSTADAS)", "pages": [144]},
    {"name": "POKE BOWL DE ATÚN", "pages": [145]},
    {"name": "ROLLITOS DE ATÚN RELLENOS DE PALMITO Y AGUACATE", "pages": [146]},
    {"name": "TOSTADAS DE SALPICÓN DE TRUCHA AHUMADA", "pages": [147]},
    {"name": "COLIFLOR TERIYAKI", "pages": [148]},
    {"name": "YAKIMESHI DE COLIFLOR CON VERDURAS", "pages": [149]},
    {"name": "VERDURAS AL GRILL CON BURRATA", "pages": [150]},
    {"name": "PORTOBELLO RELLENO DE JITOMATE, PAVO Y QUESO DE CABRA", "pages": [151]},
    {"name": "BOWL DE YOGURT GRIEGO CON BERRIES O CEREZAS Y NUECES", "pages": [152]},
    {"name": "TÁRTARA DE HONGOS CON MANTEQUILLA DE SOYA, AJO Y LIMÓN", "pages": [153]},
    {"name": "BOWL DE SALMÓN TERIYAKI", "pages": [154]},
    {"name": "SÁNDWICH DE PAVO GRIEGO", "pages": [155]},
    {"name": "SÁNDWICH DE SALMÓN MARINADO", "pages": [156]},
    {"name": "NOODLES ZUCCHINI/PALMITO CON JITOMATE ROSTIZADO Y QUESO DE CABRA", "pages": [157]},
    {"name": "QUINOA CON ESPÁRRAGOS CALABACITAS Y HIERBAS", "pages": [160]},
    {"name": "RISOTTO POBLANO CON BITS DE COLIFLOR (POLLO OPCIONAL)", "pages": [161]},
    {"name": "VERDURAS ASADAS", "pages": [162]},
    {"name": "ARROZ BLANCO", "pages": [163]},
    {"name": "ESPÁRRAGOS CON AJONJOLÍ Y PONZU", "pages": [164]},
    {"name": "EJOTES CON ALMENDRAS", "pages": [165]},
    {"name": "COLIFLOR ROSTIZADA CON PISTACHE, DÁTIL Y TAHINI", "pages": [166]},
    {"name": "PAPITAS CON ORÉGANO", "pages": [167]},
    {"name": "ARROZ SALVAJE CON CHAMPIÑONES", "pages": [168]},
    {"name": "ARROZ DE COLIFLOR CON CILANTRO", "pages": [169]},
    {"name": "CAMOTE ROSTIZADO CON ROMERO", "pages": [170]},
    {"name": "QUINOA CON ESPÁRRAGOS, HIERBAS Y ALMENDRA", "pages": [171]},
    {"name": "LENTEJA Y ARROZ SALVAJE CON HONGOS, FETA, NUEZ", "pages": [172]},
    {"name": "PAPITAS CAMBRAY ADOBADAS", "pages": [173]},
    {"name": "PAPITAS CAMBRAY CON ALCACHOFA, MOSTAZA, ALCAPARRAS Y ROMERO", "pages": [174]},
    {"name": "ARROZ DE COLIFLOR", "pages": [175]},
    {"name": "FRIJOLES DE LA OLLA ESTILO \"MESA SANA\"", "pages": [176]},
    {"name": "QUINOA", "pages": [177]},
    {"name": "TZATZIKI SIN GRASA", "pages": [178]},
    {"name": "BERENJENAS CON BALSÁMICO MOSTAZA, TOMILLO Y MIEL", "pages": [179]},
    {"name": "MUFFINS DE ZANAHORIA SALUDABLES", "pages": [182]},
    {"name": "MUFFINS DE BLUEBERRY SIN HARINA", "pages": [183]},
    {"name": "PANQUÉ DE CHOCOLATE Y PLÁTANO", "pages": [184]},
    {"name": "FRAPPÉ DE PEPINO CON TAJÍN", "pages": [185]},
    {"name": "JAMAICA SNACK", "pages": [186]},
    {"name": "PALETAS DE MANGO CON YOGURT", "pages": [187]},
    {"name": "BARK DE YOGHURT", "pages": [188]},
    {"name": "SORBETE DE FRESA", "pages": [189]},
    {"name": "GELATINA DE YOGHURT CON BERRIES", "pages": [190]},
    {"name": "CENTROS DE DONA KETO SABOR CHURRO", "pages": [191]},
    {"name": "BANANA BREAD SIN AZÚCAR", "pages": [192]},
    {"name": "CARPACCIO DE MANZANA", "pages": [193]},
]

SYSTEM_PROMPT = """You are extracting recipe data from Mexican cookbook pages for a bilingual wellness app.

Extract EXACTLY what is on the page — do not invent, summarize, or paraphrase.
Return ONLY valid JSON matching this schema exactly — no markdown, no extra text.

SCHEMA:
{
  "name_es": "exact Spanish name as printed",
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
- equiv values: use strings like "0", "1", "1/2", "1.5"
- ingredients_es/en: always an array even if only one group (with label: null)
- instructions_es/en: always an array even if only one group (with label: null)
- If a page says CONTINUACIÓN it is the continuation of a multi-page recipe — extract all content across all provided pages as one recipe
- Translate ingredient terms: jitomate→tomato, cebolla→onion, aguacate→avocado, poro→leek, elote→corn, cda→tbsp, cdita→tsp, taza→cup, nopal→cactus paddle, jocoque→sour cream, queso panela→panela cheese, queso de cabra→goat cheese, champiñón→mushroom, calabaza/calabacita→zucchini, jitomate saladet→roma tomato, chile serrano→serrano pepper, chile chipotle→chipotle pepper
- Translate section headers: INGREDIENTES→INGREDIENTS, PROCEDIMIENTO→INSTRUCTIONS, PARA LA SALSA→FOR THE SAUCE, PARA EL→FOR THE, PARA SERVIR→TO SERVE, PARA DECORAR→TO GARNISH, PARA LA VINAGRETA→FOR THE DRESSING, PARA EL ADEREZO→FOR THE DRESSING
"""


def load_image_b64(page_num: int):
    path = os.path.join(PAGES_DIR, f"page_{page_num:03d}.jpeg")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_recipe(client: anthropic.Anthropic, name: str, pages: list) -> dict:
    content = []
    for page_num in pages:
        b64 = load_image_b64(page_num)
        if b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}
            })

    content.append({
        "type": "text",
        "text": f'Extract the recipe "{name}" from the provided page image(s). Return only the JSON.'
    })

    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )

    raw = resp.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()
    return json.loads(raw)


def main():
    client = anthropic.Anthropic()

    # Load existing progress
    results = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            results = json.load(f)
        print(f"Resuming — {len(results)} recipes already done")

    total = len(RECIPES_WITH_PAGES)
    errors = []

    for i, recipe in enumerate(RECIPES_WITH_PAGES):
        name = recipe["name"]

        if name in results:
            continue

        pages = recipe["pages"]
        print(f"[{i+1:3d}/{total}] {name[:60]}...", end="", flush=True)

        try:
            data = extract_recipe(client, name, pages)
            results[name] = data
            print(" ✓")
        except json.JSONDecodeError as e:
            print(f" ✗ JSON error: {e}")
            errors.append(name)
            time.sleep(1)
            continue
        except Exception as e:
            print(f" ✗ {e}")
            errors.append(name)
            time.sleep(2)
            continue

        # Checkpoint save
        if len(results) % CHECKPOINT_EVERY == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"    → checkpoint saved ({len(results)} done)")

        time.sleep(SLEEP_BETWEEN)

    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Done! {len(results)}/{total} recipes saved to {OUTPUT_FILE}")
    if errors:
        print(f"Failed ({len(errors)}): {', '.join(errors[:10])}")
    print("Upload recipes_bilingual.json here to bake into the app.")


if __name__ == "__main__":
    main()
