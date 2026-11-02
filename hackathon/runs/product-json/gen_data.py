#!/usr/bin/env python3
"""Synthesize messy product listings from SAMPLED gold attributes.
Gold = the sampled values (not model opinions). glm-5p3 only writes the prose.
A regex check verifies every non-null gold value literally appears in the text; rows that fail are dropped.
Usage: python3 gen_data.py --batches 96 --per 5 --out raw/gen_raw.jsonl
"""
import argparse, json, os, random, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fw

GEN_MODEL = "accounts/fireworks/models/gpt-oss-120b"
SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "schema.json")))
TYPES = SCHEMA["properties"]["product_type"]["enum"]
COLORS = [c for c in SCHEMA["properties"]["color"]["enum"] if c]
MATERIALS = [m for m in SCHEMA["properties"]["material"]["enum"] if m]
BRANDS = json.load(open(os.path.join(os.path.dirname(__file__), "raw", "esci_brands.json")))

APPAREL = {"t-shirt", "hoodie", "jacket", "dress"}
SIZES = {
    **{t: ["XS", "S", "M", "L", "XL", "XXL"] for t in APPAREL},
    "jeans": ["28", "30", "32", "34", "36", "38"],
    "sneakers": ["6", "7", "8", "9", "10", "11", "12", "13"], "boots": ["6", "7", "8", "9", "10", "11", "12", "13"],
    "bed sheets": ["Twin", "Full", "Queen", "King"], "bath towel": [None, "27x54", "30x56"],
    "water bottle": ["18oz", "24oz", "32oz", "40oz"], "coffee mug": ["11oz", "15oz", "20oz"],
    "dog leash": ["4ft", "6ft"], "yoga mat": ["4mm", "6mm", "8mm"], "notebook": ["A5", "A4", "B5"],
}
MATS = {
    "t-shirt": ["cotton", "polyester", "linen"], "hoodie": ["cotton", "polyester"], "jacket": ["polyester", "leather", "nylon", "wool", "cotton"],
    "jeans": ["cotton"], "dress": ["cotton", "polyester", "linen"], "sneakers": ["canvas", "leather", "nylon"], "boots": ["leather", "nylon"],
    "backpack": ["nylon", "canvas", "polyester", "leather"], "wallet": ["leather", "canvas", "nylon"], "sunglasses": ["plastic", "aluminum", "wood"],
    "watch": ["stainless steel", "leather", "silicone", "wood"], "headphones": ["plastic", "aluminum"], "phone case": ["silicone", "plastic", "leather", "wood"],
    "water bottle": ["stainless steel", "plastic", "glass", "aluminum"], "coffee mug": ["ceramic", "stainless steel", "glass", "bamboo"],
    "blender": ["plastic", "stainless steel", "glass"], "desk lamp": ["aluminum", "wood", "plastic"], "office chair": ["leather", "nylon", "plastic"],
    "bed sheets": ["cotton", "linen", "bamboo", "polyester"], "bath towel": ["cotton", "bamboo"], "yoga mat": ["silicone", "plastic"],
    "dog leash": ["nylon", "leather"], "candle": ["glass", "ceramic"], "notebook": ["leather", "linen"],
}
PRICE = {"t-shirt": (9, 40), "hoodie": (25, 90), "jacket": (40, 250), "jeans": (25, 120), "dress": (20, 150), "sneakers": (35, 180), "boots": (50, 260),
         "backpack": (20, 160), "wallet": (12, 120), "sunglasses": (10, 200), "watch": (25, 400), "headphones": (15, 350), "phone case": (6, 45),
         "water bottle": (10, 45), "coffee mug": (8, 30), "blender": (25, 300), "desk lamp": (15, 120), "office chair": (80, 500), "bed sheets": (20, 150),
         "bath towel": (8, 50), "yoga mat": (15, 110), "dog leash": (8, 40), "candle": (8, 45), "notebook": (5, 35)}
BUNDLE_EXTRAS = {"headphones": "a carrying case and an aux cable", "watch": "an extra strap and a screen protector", "phone case": "a tempered-glass screen protector",
                 "water bottle": "two extra lids and a cleaning brush", "blender": "a recipe book and a travel cup", "yoga mat": "a carry strap and two yoga blocks",
                 "desk lamp": "a USB-C cable and a pen holder", "dog leash": "a matching collar and poop-bag holder", "backpack": "a pencil case and a rain cover",
                 "candle": "a wick trimmer and a snuffer", "notebook": "a pen and a sticker sheet", "coffee mug": "a coaster and a spoon",
                 "bed sheets": "two pillowcases and a fitted sheet (sheet set)", "sneakers": "an extra pair of laces and a shoe bag", "wallet": "a keychain and a gift box"}


def sample_spec(rng):
    t = rng.choice(TYPES)
    brand = rng.choice(BRANDS)
    color = None if rng.random() < 0.12 else rng.choice(COLORS)
    sizes = SIZES.get(t)
    size = rng.choice(sizes) if sizes else (None if rng.random() < 0.7 else "One Size")
    if size is not None and t not in APPAREL and t not in ("jeans", "sneakers", "boots", "bed sheets") and rng.random() < 0.25:
        size = None
    material = None if rng.random() < 0.22 else rng.choice(MATS[t])
    lo, hi = PRICE[t]
    price = None if rng.random() < 0.18 else round(rng.uniform(lo, hi) - 0.01, 2)
    if price is not None and rng.random() < 0.3:
        price = float(int(price) + 1)  # whole-dollar prices too
    qty = 1 if rng.random() < 0.72 else rng.choice([2, 2, 3, 4, 6, 12])
    bundle = t in BUNDLE_EXTRAS and rng.random() < 0.28
    gold = {"brand": brand, "product_type": t, "color": color, "size": size, "material": material, "price_usd": price, "quantity": qty, "is_bundle": bundle}
    noise = {
        "alt_colors": color is not None and rng.random() < 0.4,
        "was_price": price is not None and rng.random() < 0.45,
        "shipping": rng.random() < 0.3,
        "size_range": size is not None and rng.random() < 0.3,
        "caps": rng.random() < 0.2, "emoji": rng.random() < 0.3, "typos": rng.random() < 0.3, "keyword_stuffing": rng.random() < 0.35,
        "brand_style": rng.choice(["plain", "by_brand", "trademark", "lowercase_mention", "end_of_text"]),
        "qty_style": rng.choice(["pack of N", "N-pack", "set of N", "N pcs", "(N count)", "N units"]),
        "length": rng.choice(["short (40-70 words)", "medium (80-130 words)", "long (150-220 words)"]),
    }
    return gold, noise


def instructions(i, gold, noise, rng):
    facts = [f"brand: {gold['brand']} (spell it exactly like this at least once; you may also write it in a different case elsewhere)",
             f"product type: {gold['product_type']} (describe it as this kind of item; you may use synonyms too)",
             f"color sold: {gold['color']} (use this exact color word)" if gold["color"] else "color: do NOT mention any color at all",
             f"size sold: {gold['size']} (write it exactly, e.g. 'Size: {gold['size']}')" if gold["size"] else "size: do not state any size",
             f"material: {gold['material']} (use this exact word)" if gold["material"] else f"material: do NOT mention any material from this list: {', '.join(MATERIALS)}",
             f"current price: ${gold['price_usd']:.2f} (write it exactly as ${gold['price_usd']:.2f})" if gold["price_usd"] is not None else "price: do not mention any price or dollar amount",
             f"quantity: {gold['quantity']} identical units, written as '{noise['qty_style'].replace('N', str(gold['quantity']))}' (must include the digit {gold['quantity']})" if gold["quantity"] > 1 else "quantity: a single unit; do not write 'pack of', 'set of', '-pack' or 'count'",
             f"bundle: yes, it comes WITH {BUNDLE_EXTRAS[gold['product_type']]} (different item types sold together)" if gold["is_bundle"] else "bundle: no, nothing else is included; do not use the words 'kit', 'bundle', 'comes with', or 'includes'"]
    extras = []
    if noise["alt_colors"]:
        others = rng.sample([c for c in COLORS if c != gold["color"]], 2)
        extras.append(f"mention that it is 'also available in {others[0]} and {others[1]}' (distractor; the item sold is {gold['color']})")
    if noise["was_price"]:
        was = round(gold["price_usd"] * rng.uniform(1.2, 1.8), 2)
        extras.append(f"show an old crossed-out/list price of ${was:.2f} and/or 'save ${was - gold['price_usd']:.2f}' (distractor; the current price is ${gold['price_usd']:.2f})")
    if noise["shipping"]:
        extras.append(f"mention a shipping cost like '+ ${rng.choice([3.99, 4.95, 5.99, 7.49]):.2f} shipping' or 'free shipping over $35' (distractor)")
    if noise["size_range"]:
        extras.append(f"mention that the product line comes in a range of sizes (e.g. 'available XS-XXL' or 'sizes 6-13'), but this listing sells size {gold['size']}")
    if noise["caps"]:
        extras.append("write the title line in ALL CAPS")
    if noise["emoji"]:
        extras.append("use 2-4 emojis")
    if noise["typos"]:
        extras.append("include 2-3 natural typos (but NOT in the brand, color, size, material or price)")
    if noise["keyword_stuffing"]:
        extras.append("end with an SEO keyword-stuffing line of comma-separated search terms (do not add other colors or materials from the lists there)")
    style = {"plain": "brand at the start of the title", "by_brand": "brand introduced as 'by <brand>' mid-text", "trademark": "brand written with ® or ™ attached",
             "lowercase_mention": "brand mentioned only in a lowercase sentence like 'another great product from <brand>' (still spelled the same letters)",
             "end_of_text": "brand only mentioned in the last sentence"}[noise["brand_style"]]
    return (f"Listing {i}: length {noise['length']}. Facts that MUST be embedded exactly:\n- " + "\n- ".join(facts) +
            f"\n- brand placement: {style}\nNoise to add: " + ("; ".join(extras) if extras else "none") +
            "\nDo not mention any other brand name.")


SYSTEM = ("You write realistic, messy e-commerce product listings the way small sellers paste them into marketplaces: a title line, then a blurb/bullets. "
          "Vary voice and formatting between listings. Follow every fact and noise instruction literally. Never include any color, material, or product type from the schema lists other than the ones you are told to use. "
          "Return JSON: {\"listings\": [\"...\", \"...\"]} with one string per listing, in order, and nothing else.")
RF = {"type": "json_schema", "json_schema": {"name": "listings", "schema": {"type": "object", "properties": {"listings": {"type": "array", "items": {"type": "string"}}}, "required": ["listings"]}}}


def verify(text, gold):
    """Every non-null gold value must literally appear; null fields must not be contradicted."""
    low = text.lower()
    probs = []
    if gold["brand"].lower() not in low: probs.append("brand missing")
    if gold["color"]:
        if not re.search(r"\b" + re.escape(gold["color"]) + r"\b", low): probs.append("color missing")
    else:
        hit = [c for c in COLORS if re.search(r"\b" + re.escape(c) + r"\b", low)]
        if hit: probs.append(f"null color but found {hit}")
    if gold["size"]:
        if gold["size"].lower() not in low: probs.append("size missing")
    if gold["material"]:
        if not re.search(r"\b" + re.escape(gold["material"]) + r"\b", low): probs.append("material missing")
    else:
        hit = [m for m in MATERIALS if re.search(r"\b" + re.escape(m) + r"\b", low)]
        if hit: probs.append(f"null material but found {hit}")
    if gold["price_usd"] is not None:
        if f"${gold['price_usd']:.2f}" not in text and f"${gold['price_usd']:.0f}" not in text: probs.append("price missing")
    else:
        if "$" in text or re.search(r"\b\d+\.\d\d\b", text): probs.append("null price but $ found")
    if gold["quantity"] > 1:
        if not re.search(r"\b" + str(gold["quantity"]) + r"\b", text): probs.append("qty digit missing")
    else:
        if re.search(r"\b(pack of|set of|\d+-pack|\d+ pack|count\))", low): probs.append("qty 1 but pack language")
    if not gold["is_bundle"] and re.search(r"\b(bundle|kit|comes with|bundled)\b", low): probs.append("non-bundle but bundle language")
    if re.search(r"\b(typos?|distractor|noise|instruction|as requested|listing \d)\b", low): probs.append("instruction leak")
    # other product types may appear as context ("pairs with jeans"); allowed. The title line must not name another type.
    title = low.split("\n")[0]
    others = [t for t in TYPES if t != gold["product_type"] and re.search(r"\b" + re.escape(t) + r"s?\b", title)]
    if others: probs.append(f"other type in title {others}")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=96)
    ap.add_argument("--per", type=int, default=5)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="raw/gen_raw.jsonl")
    ap.add_argument("--start", type=int, default=0, help="batch index to start at (resume)")
    ap.add_argument("--end", type=int, default=0, help="batch index to stop before (0 = all)")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    specs = [[sample_spec(rng) for _ in range(a.per)] for _ in range(a.batches)]
    kept = dropped = 0
    with open(a.out, "a") as f:
        for b in range(a.start, a.end or a.batches):
            user = "\n\n".join(instructions(i + 1, g, n, rng) for i, (g, n) in enumerate(specs[b]))
            try:
                content, _, lat, ti, to, fin = fw.chat(GEN_MODEL, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                                                      max_tokens=6000, temperature=0.9, response_format=RF, note="gen")
                listings = json.loads(content)["listings"]
            except fw.CapReached as e:
                print("CAP:", e); break
            except Exception as e:
                print(f"batch {b} failed: {e}"); continue
            for i, (g, n) in enumerate(specs[b]):
                if i >= len(listings): break
                text = listings[i].strip()
                probs = verify(text, g)
                row = {"id": f"pj-{b:03d}-{i}", "text": text, "gold": g, "noise": n, "verify": probs}
                f.write(json.dumps(row) + "\n"); f.flush()
                if probs: dropped += 1
                else: kept += 1
            print(f"batch {b}: {len(listings)} listings, {lat:.1f}s, {ti}+{to} tok, fin={fin}; kept so far {kept}, dropped {dropped}, spend ${fw.ledger_total():.3f}")
    print(f"done. kept {kept}, dropped {dropped}, spend ${fw.ledger_total():.3f}")


if __name__ == "__main__":
    main()
