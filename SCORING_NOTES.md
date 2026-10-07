# Scoring notes

A running list of scores that look wrong, what the data says, and what would fix them.
**APPLIED 2026-10-02 (user: "Apply both A B C"):** variants A, B and C below are now in
scripts/scorer.py and scripts/flagged_ingredients.json, plus the A6 size fix (sibling repair in
merge_off_into_catalog.py: 524 ingredient lists and 301 nutrition panels taken from a
ShopRite-sourced size of the same product). A7 also applied (overnight 2026-10-03): non-English Open Food Facts lists are rejected (24 products, now unscored until their ShopRite page is fetched; the night fetch queues them early). Still open: A9/A10,
74 size groups still 15+ apart, stevia/monk fruit, 100% juice sugar. New research goes to research/. Do not tune the scorer to one product:
find the general rule, then check it against the whole catalog with
`python3 scripts/whatif_scoring.py`, which re-scores all ~16,700 products in memory and
prints before/after without writing anything.

---

# Audit 2026-10-02 (Opus deep dive)

Method: detectors run over every scored product (full_catalog_scored.json + the enriched
ingredient lists), then the proposed fixes simulated over the whole catalog. The simulation's
baseline reproduces every stored score exactly (0 of 16,695 drift), so the before/after
numbers below are real, not estimates.

## Findings, worst first

| # | Problem | Products | Example (score today) | Cause |
|---|---|---|---|---|
| A1 | **Artificial sweeteners are never flagged** | 1,031 | Sucralose sweetener packets **83.8**; Gold Peak Zero Sugar tea 75.2; Sprite Zero Sugar **59.4** (above Olipop and every real-sugar soda) | No flagged category for aspartame, sucralose, acesulfame, saccharin. Swapping sugar for sucralose *raises* a score |
| A2 | **Sugars under other names are not "added sugar"** | ~200 that matter (+817 "juice concentrate", mostly legitimate) | Olipop **57.2** vs Poppi 37.8: Olipop's cassava root syrup isn't recognised as sugar; Poppi's "cane sugar" is | Term list misses cassava/tapioca/brown rice/agave/maple/date/malt syrups, cane juice, sweetening juice concentrates |
| A3 | **Sugar snap peas scored as sugar** | 7 | Plain frozen sugar snap peas **40** (the 15 oz bag of the same peas: 100) | "sugar" matches inside "sugar snap" in the flag check, and the first-ingredient-is-sugar cap (40) fires on it too. Also "honeydew" trips "honey" (1 product) |
| A4 | **Fortification vitamins counted as ingredients** | 625 (median simplicity **0**) | Elbow macaroni 60.5; pasta of every brand 50-65 with nothing flagged | "semolina, niacin, iron, thiamine mononitrate, riboflavin, folic acid" is 6 ingredients to the simplicity count. Enrichment is required by law, not a recipe choice |
| A5 | **Simplicity counts ingredients, not what they are** | most of the catalog; 288 products with *nothing flagged* sit below 65 because of it | **Poppi** (10 plain ingredients) gets simplicity **0**; Coca-Cola (6, incl. HFCS, caramel colour, phosphoric acid) gets 52. Marinara, salsa, broth, soups all hit hard | -12 per ingredient after the first, whether it's "garlic" or "sodium stearoyl lactylate". Water counts too (5,503 products) |
| A6 | **Same product, different size, very different score** | 80 groups, 15-60 points apart | Progresso bread crumbs 6.4 vs **60.5**; Totino's pizza rolls 9 vs **62.4**; Betty Crocker cookie mix 4.5 vs 52.5 | One size's Open Food Facts record has a truncated ingredient list ("sea salt, spices, sugar…" with the breadcrumbs missing), so it looks simple |
| A7 | **Ingredient lists in French/Spanish/German/Norwegian** | 23 | V8 **80** (list in French); Cholula, Sriracha, Kraft tartar sauce, Cookie Crisp | Open Food Facts returned a non-English list; English flag words ("sugar", "oil") never match "sucre", "zucker", "huile" |
| A8 | **"(preservative)" after a vitamin** | ~30 | citric acid (preservative), tocopherols (preservative) | The bare word "preservative" is a flag term. It also, usefully, catches real ones the list lacks: potassium benzoate, sulfites, EDTA, parabens - add those by name before removing the bare word |
| A9 | **Salt scores 93-95** | ~6 | Cento sea salt 95.1, Morton 92.9 (with a high-sodium banner) | Pure single ingredient, nothing flagged. Arguably fine as "what it is"; flagged here as a judgement call |
| A10 | **Date syrup / date sugar score 100** | 2 | Let's Date syrup 100 | The sugar cap exempts whole fruit, and these list "dates". It is a sweetener in use. Judgement call |
| A11 | **NOVA 1 inferred for 7-10 ingredient pouches** | 22 | GoGo squeeZ fruit-and-veg pouches | Inferred from siblings; small effect |

## Proposed fixes and what they do (simulated over the whole catalog)

**Variant A - targeted fixes, low risk:** A1 (new flag "artificial sweetener", severity 2),
A2 (add the syrup names to added sugar), A3 (ignore "sugar snap"/"honeydew"), A4 (enrichment
vitamins and plain water don't count toward simplicity), A8 (antioxidant "(preservative)"
ignored). **3,606 products move**; 2,471 up (median +3.6, mostly pasta), 1,135 down
(median -10.2, almost all diet/zero-sugar products).

**Variant B - A plus "what is it, not how many":** each ingredient after the first costs 5 points
if it is a kitchen ingredient (juice, vinegar, garlic, tomatoes, flour, milk, spices…) and 12 if it
is anything else (gums, syrups, starches, acids, colours, flavours, isolates). **7,261 move**,
6,131 up. Junk does not move: Oreo 9.6, Doritos 14.2, Froot Loops 29, chips median 22,
cookies 10.5 -> 11.1, frozen meals 13.2 unchanged.

| Product | Today | A | B |
|---|---|---|---|
| Poppi Cream | 37.8 | 39.0 | **45.3** |
| Poppi Grape | 40.1 | 40.1 | **47.6** |
| Olipop Cream Soda | 57.2 | 47.0 | 47.0 |
| Coca-Cola Original | 37.5 | 41.1 | 41.1 |
| Coca-Cola Zero Sugar | 42.0 | 32.4 | 32.4 |
| Sprite Zero Sugar | 59.4 | 49.1 | 49.1 |
| Sucralose sweetener | 83.8 | 71.8 | 71.8 |
| Gold Peak Zero Sugar tea | 75.2 | 65.0 | 65.0 |
| Sugar snap peas (8 oz) | 40 | **100** | **100** |
| San Giorgio elbow macaroni | 60.5 | 69.9 | 74.9 |
| Rao's marinara | 66.4 | 66.4 | **79.0** |
| Swanson chicken broth | 40.8 | 40.8 | 51.3 |
| Heinz ketchup | 47.4 | 47.4 | 51.5 |
| Banana / plain Greek yogurt / natural PB | 99.9 / 94.1 / 98.3 | same | same |
| Oreo / Doritos / Froot Loops | 9.6 / 14.2 / 29.0 | same | same |

Category medians, today -> B: red sauces 52.8 -> 63.4, salsa 47.9 -> 55.2, broth 45.1 -> 50.9,
spaghetti 65.3 -> 77.3, lemon-lime soda 36.9 -> 31.8, cola 41.1 -> 40.0, cereal 37.4 -> 37.5.

**On Poppi specifically:** under B it lands at 45-48, above regular Coke (41) and diet colas
(32), level with Olipop (47) and Sprite Zero (49). It does not go higher because it really does
have 10 g of added cane sugar in the cream flavour (the "High in added sugar" banner) and NOVA
classes it ultra-processed. That is probably the honest ceiling for a sweetened soda.

**Not fixed by A or B (need their own work):**
- A6 size mismatches: fix by preferring ShopRite's first-party list, or by copying the longest
  list across sizes of the same product when one size's list is a strict subset (truncated).
- A7 foreign-language lists: reject a non-English Open Food Facts list the way junk panel text is
  already rejected (`looks_like_panel_residue`), so the product falls back to unscored until the
  ShopRite page is fetched.
- A9/A10: decide whether a pure culinary ingredient (salt) or a fruit-based sweetener (date syrup)
  should be capped like sugar is.

## Decisions for the user

1. Apply **A** (targeted, ~3,600 products move, almost all corrections)? Recommended.
2. Also apply **B** (bigger shift, ~7,300 move; fixes the Poppi/Coke ordering)? Recommended, with
   the kitchen-word list reviewed first - it decides what counts as "real food".
3. Flag **stevia, monk fruit, allulose, erythritol**? Not in A or B. They are not sugar and not
   artificial; flagging them is a philosophy call (Olipop and Poppi both use stevia).
4. Should a sweetened drink have a ceiling, the way bacon has 50?

---

## User report 1. Poppi prebiotic soda scores too low (2026-10-02) - see audit A2/A5 above

**What the user said:** the cream soda version scores 38 and they don't think the
ingredients are too bad, even though there are a lot of them.

**What the data says (full_catalog_scored.json):**
- Poppi Prebiotic Soda Cream: **37.8**. Orange Cream: **39.2**. Grape and Cherry Cola: **40.1**.
- Ingredients (cream soda): sparkling water, cassava root fiber, organic cane sugar, white grape
  juice concentrate, natural flavors, organic apple cider vinegar, organic agave inulin,
  natural lactic acid, stevia leaf extract, natural tartaric acid.
- Sub-scores: `ingredient_simplicity` **0**, `flagged_ingredients` 64 (matches: *added sugar*,
  *added flavoring*), `nutrition` 67–78 (the cream soda also carries the "High in added sugar"
  banner at 10.6 g), `external_processing` 15.
- For comparison in the same category: Coca-Cola Original **37.5**, Pepsi Cola 27–36, Sprite 37,
  **Olipop 50–57**, Sprite Zero Sugar ~60, Coke Zero 42. So Poppi lands at regular-cola level.

**Why it probably looks wrong:**
1. **Simplicity is 0 because of ingredient COUNT.** Ten items is penalised the same whether they
   are additives or things like sparkling water, apple cider vinegar and stevia leaf. The count
   does not look at what the items are. This is the main thing to revisit: weigh simplicity by
   how recognisable/processed each ingredient is, not just how many there are.
2. **"Natural flavors" is flagged** (*added flavoring*) along with the sugar flag. That may be
   right, but it is worth checking how hard it is penalised relative to artificial sweeteners
   and colours in the same list (Poppi has none of those; Coke Zero has several).
3. **`external_processing` 15** looks like a NOVA-style "ultra-processed" mark inferred from the
   category or brand. Check whether it fires for Poppi from real data or from the soda category
   default, since it gives every soda the same 15.
4. **Nutrition is mixed:** 4–5 g added sugar is real, and some of the fiber is "added fiber".
   The honest answer may be that it should score above Coke and Pepsi but below water.

**Questions to settle before changing anything:**
- Should "contains added sugar" cap a soda at a set ceiling the way the processed-meat cap works?
- Should a short, recognisable list of ten beat a short list of four additives?
- Does Olipop (50–57) sitting 15–20 points above Poppi make sense, given similar lists?

**Where to look:** `scripts/scorer.py` (`ingredient_simplicity`, `flagged_ingredients`,
`external_processing`), `scripts/flagged_ingredients.json` (added sugar / added flavoring),
`scripts/category_facts.json`. After any change run `rescore_all.py`, `price_signal.py`,
`build_app_data.py`, then compare the soda category before and after.

---

## Variant C (2026-10-02): Poppi must be far above Coke (user)

The user accepted B in principle but: "in no universe should Poppi only be 7 points above Coke."
The data says why B can't do it: Coke's **39 g of added sugar per can (78% of the daily value)**
moves its score almost nothing. Nutrition is 10% of the score, and the 39 g is averaged with
Coke's low sodium. The scorer judges the ingredient LIST and barely looks at the DOSE.

Evidence used:
- Sugar-sweetened drinks, per extra serving a day: type 2 diabetes risk +27%, cardiovascular
  disease +9%, all-cause mortality +10% (dose-response meta-analysis, Nutrients 2021, PMC8402166).
- Colas specifically (not other sodas) linked to 3.7-5.4% lower hip bone density in older women;
  phosphoric acid suspected (Framingham Osteoporosis Study, Tucker et al., AJCN 2006).
- Caramel colour: 4-MEI is IARC Group 2B; Coca-Cola reformulated and tested low (Consumer
  Reports 2014). Already flagged as "added color".
- Poppi: ~5 g sugar (2-3 g added) per can; one flavour in our data says 10.6 g - worth checking.

**C = B + added-sugar dose cap + phosphoric acid flag (severity 1):**
- added sugar >= 25 g per serving (a whole day's limit in one serving): **cap 15**
- >= 15 g: cap 30
- >= 10 g (FDA "high in added sugar"): cap 45

| Product | Today | B | C |
|---|---|---|---|
| Poppi Grape / Orange Cream / Cream | 40.1 / 39.2 / 37.8 | 47.6 / 46.7 / 45.3 | **47.6 / 46.7 / 45.0** |
| Olipop Cream Soda | 57.2 | 47.0 | 47.0 |
| Coca-Cola Original | 37.5 | 41.1 | **15** |
| Pepsi / Sprite | 30.3 / 38.4 | 36.0 / 42.0 | **15 / 15** |
| Coca-Cola Zero Sugar | 42.0 | 32.4 | 27.2 |
| Sprite Zero Sugar | 59.4 | 49.1 | 49.1 |
| Tropicana 100% OJ (no ADDED sugar) | 100 | 100 | 100 |

978 products are lowered by C (colas, sweet teas, sodas, sports drinks, ice cream, candy,
sweetened condensed milk). Medians: cola 41 -> 31, lemon-lime soda 37 -> 22, iced tea 48 -> 30.

Open question C raises: 100% juice has no ADDED sugar, so it is untouched (Tropicana stays 100).
Whether juice's own sugar should count is a separate decision.

## 2026-10-03: NOVA counts only when it says ultra-processed (owner decision, "option C")

Found from the owner's question: BelGioioso sliced fresh mozzarella (milk, vinegar, enzymes, salt)
scored 87 and Bowl & Basket sliced part-skim mozzarella 96. ~7 of the 9 points were NOVA: the
BelGioioso had an Open Food Facts grade of 3 (all cheese is NOVA 3) and the Bowl & Basket had
none, so its processing sub-score was skipped. Whether a grade existed was swinging similar foods.

Options simulated on the whole catalog (in memory first):
- A: fill missing NOVA from the category's majority - too blunt (a tomahawk steak -20, tea bags -14).
- B: NOVA 3 worth 70 instead of 50 - shrinks the gap, doesn't remove it.
- C (applied): NOVA 1-3 are not applicable; NOVA 4 still scores 15. Our own ingredient analysis
  already covers 1-3, and OFF mis-grades some ultra-processed products as 1-2.

Result: 2,154 products moved 0.5+ points, 1,341 up and 813 down. BelGioioso mozzarella 87.2 -> 93.8
(Bowl & Basket unchanged at 96.2). Down: PediaSure -13.7, Ken's Russian dressing -13.4, Chobani
Flip -11.9 (OFF had them as minimally processed). Up: sauerkraut, clam juice, tofu, crushed
tomatoes +8.6 (simple foods that NOVA files as "processed").

## 2026-10-06: label footnotes are no longer counted as ingredients (bug fix)

From the 2026-10-04 score audit: 32 labels end with "*an ingredient not found in regular milk"
(or orange juice / yogurt), and that footnote was counted as an extra ingredient. scorer.py now
drops it before scoring; the marked ingredients themselves still count. 20 products moved up
1.5-1.8 points (orange juices, lactose-free and DHA milks). Not a rule change.

Also applied 2026-10-06 (data sanity, not a rule change): added-sugar figures that can't be true are
treated as unknown - more added than total sugar, or 1 g+ on a product named zero sugar / sugar free /
no sugar added / unsweetened. 10 products moved, e.g. Mountain Dew Zero Sugar 15 -> 31.8 (it carried
44 g "added sugar"), La Choy teriyaki 30 -> 45.9 (19 g added vs 1 g total).

Simulated and NOT applied (as written they hit the wrong products):
- "Cap panel-less products at 90" would drop 650 products, mostly fresh produce, spices and water
  that rightly have no panel. Narrowed to 4+ ingredients, not produce/spice/water: 8 products
  (Rummo orzo, Indian Head corn meal, mustards, a broth, baby corn) - owner's call.
- "Ignore OFF added sugar when the ingredients show none" would raise 51, including Talenti gelato
  15 -> 36 whose lists are simply truncated. Only the impossible-value version above was applied.

Audit proposals still waiting on the owner (see audit/reports/2026-10-04-review.md):
- the narrowed 8-product panel cap above;
- Vita Coco 16.9 oz (45 vs 90.9 for the 33.8 oz): OFF lists natural sugar as added; needs a manual fix;
- 5 nutrition panels with impossible numbers need a manual correction or removal.
