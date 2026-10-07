"""
Scoring engine. Computes independent sub-scores (never pre-blended) and
combines them per a profile's weights into a single 0-100 score.

Sub-scores:
  - ingredient_simplicity: fewer top-level ingredients + less nested
    complexity = closer to "just peanuts."
  - flagged_ingredients: penalizes added sugar, added/hydrogenated oil,
    emulsifiers, artificial preservatives - the things a label-reader
    would actually squint at.
  - nutrition: added sugar (g), sodium (mg), saturated fat (g) per
    serving. Deliberately excludes calories - whole peanuts are
    calorie-dense but that's not a processing signal.
"""
import json
import re
from pathlib import Path

from ingredients import top_level_ingredients, flatten_all_mentions

SCRIPTS_DIR = Path(__file__).resolve().parent

with open(SCRIPTS_DIR / "flagged_ingredients.json") as f:
    FLAGGED_CATEGORIES = json.load(f)

with open(SCRIPTS_DIR / "category_facts.json") as f:
    CATEGORY_FACTS = json.load(f)

# Expand `_aliases` into real entries so every CATEGORY_FACTS.get(category)
# call site works unchanged. See the note in category_facts.json: ShopRite's
# real leaf categories almost never match a curated name, so fully-configured
# logic ("rice", "pasta") was sitting unused while the actual products lived
# in "white_rice" and "penne_pasta". An alias never overwrites a category that
# is curated in its own right.
for _alias, _target in (CATEGORY_FACTS.get("_aliases") or {}).items():
    if _alias not in CATEGORY_FACTS and _target in CATEGORY_FACTS:
        CATEGORY_FACTS[_alias] = CATEGORY_FACTS[_target]

# Salt doesn't meaningfully change how "processed" a product is - a
# peanuts+salt product isn't penalized for that 2nd ingredient.
_NEUTRAL_INGREDIENTS = {"salt", "sea salt"}
# Audit 2026-10-02 (A4): plain water and the vitamins the law REQUIRES in enriched flour
# and pasta were each counted as an ingredient. 625 products had 3+ enrichment vitamins
# on the list and a median simplicity of 0 - every pasta brand sat at 50-65 with nothing
# flagged. Neither is a recipe choice, so neither costs simplicity.
_NEUTRAL_INGREDIENTS |= {
    "water", "filtered water", "carbonated water", "sparkling water", "purified water", "spring water",
    "spices", "natural spices",
    "niacin", "reduced iron", "iron", "ferrous sulfate", "thiamine mononitrate", "thiamin mononitrate",
    "thiamine", "riboflavin", "folic acid", "vitamin d3", "vitamin a palmitate",
}

# Audit 2026-10-02 (B): simplicity used to cost 12 points for every ingredient after the
# first, whether it was "garlic" or "sodium stearoyl lactylate". Ten plain ingredients
# (Poppi) scored 0 while six worse ones (Coca-Cola: HFCS, caramel colour, phosphoric
# acid...) scored 52, and marinara, salsa and broth were all pulled down. Now an
# ingredient a home cook would recognise costs 5, and anything else still costs 12.
# The exclusion list wins: "corn syrup" is not "corn", "tomato powder" is not "tomato".
# Simulated over the whole catalog before applying: junk did not move (Oreo 9.6, Doritos
# 14.2, Froot Loops 29), red sauces 52.8 -> 63.4, Poppi 38 -> 45.
_KITCHEN_INGREDIENT = re.compile(
    r"\b(water|juice|vinegar|salt|spices?|herbs?|garlic|onions?|peppers?|paprika|cumin|oregano|basil|parsley|"
    r"thyme|rosemary|cinnamon|ginger|turmeric|nutmeg|tomato(es)?|lemon|lime|apples?|oranges?|berries|"
    r"strawberr(y|ies)|blueberr(y|ies)|raspberr(y|ies)|cherr(y|ies)|grapes?|banana|mango|pineapple|peach(es)?|"
    r"pears?|carrots?|celery|beets?|spinach|kale|potato(es)?|beans?|lentils|chickpeas|peas|corn|rice|oats?|"
    r"wheat|flour|semolina|barley|quinoa|milk|cream|butter|eggs?|cheese|yogurt|cultures?|enzymes|yeast|"
    r"olive oil|avocado oil|coconut( milk| oil)?|almonds?|peanuts?|cashews?|walnuts?|pecans?|seeds?|cocoa|"
    r"chocolate|vanilla( extract)?|honey|maple syrup|sugar|chicken|beef|pork|turkey|fish|salmon|tuna|shrimp|"
    r"mushrooms?|cucumbers?|squash|pumpkin|zucchini|broccoli|cabbage|lettuce|avocados?|dates|raisins|"
    r"cassava root fiber|chicory root|inulin|tea|coffee)\b", re.I)
_NOT_KITCHEN = re.compile(
    r"(modified|hydrolyzed|isolate|concentrate|syrup|fructose|dextrose|maltodextrin|starch|gum|lecithin|"
    r"acid|colou?r|caramel|flavou?r|extract(?<!vanilla extract)|powder)", re.I)
_SIMPLE_QUALIFIERS = re.compile(r"\b(organic|natural|fresh|filtered|carbonated|sparkling|pure|whole|dried|ground|\d+%)\b", re.I)
KITCHEN_INGREDIENT_COST = 5
OTHER_INGREDIENT_COST = 12

# Added 2026-09-12 after researching how other platforms score food: Yuka
# hard-caps any product containing a high-risk additive at 49/100, regardless
# of how clean everything else looks - a bad ingredient can't be "averaged
# away." Our own severity-3 tier (hydrogenated oil, mechanically separated
# meat) is the closest equivalent to Yuka's "high-risk" bucket. Checked
# against real data before adding this: at today's weights, every severity-3
# product already lands at or below 50 anyway (max observed: 56.4, one
# product, before this cap), so this changes nothing about current rankings -
# it's a documented guarantee against a hypothetical future product that
# combines a severe ingredient with an otherwise very short/clean profile,
# not a fix to an observed problem.
SEVERE_INGREDIENT_CAP = 50
# Processed meat is IARC Group 1 - the same evidence tier as tobacco smoke for
# the strength of the classification (NOT the size of the risk, which is far
# smaller). Strong ingredient or husbandry sub-scores should not be able to
# average that away, so it gets a hard ceiling like the severity-3 cap above.
# User decision 2026-09-14.
CURED_MEAT_CAP = 50
# A bottle of sunflower oil IS the seed oil - its one-ingredient label earns a
# perfect ingredient_simplicity, which is how corn oil reached 97.8 and
# safflower 98.8. Capping only when a seed oil is the FIRST ingredient hits
# the 219 products that genuinely are seed oil, without pinning the 4,998
# that merely contain some. User direction 2026-09-15: "just tank the
# sunflower oil, note that its a seed oil and flag it on the banner."
SEED_OIL_PRIMARY_CAP = 25
# A bag of granulated sugar scored 84.9, agave nectar and maple syrup 97-100.
# They earn it honestly under an ingredients-first score - one ingredient,
# nothing flagged, minimally processed - which is exactly the blind spot: the
# thing IS sugar. Same shape as the seed-oil and cured-meat caps, and it only
# binds products that would otherwise look good.
#
# Measured before choosing 40: capping at 25 would have caught 460 products
# (too broad - it reaches things that merely lead with sugar), at 60 only 142
# (leaves table sugar in the 60s). At 40, 245 products move, and sugar, agave
# and maple syrup all land where a shopper reads "this is a sweetener, not a
# health food". Deliberately less punitive than the seed-oil cap, which
# reflects a stated personal preference rather than a general one.
SWEETENER_PRIMARY_CAP = 40

# Audit 2026-10-02 (C): the score judged the ingredient LIST and barely the DOSE. Coca-Cola's
# 39 g of added sugar per can (78% of the daily value) moved it almost nothing - nutrition is
# 10% of the score and the sugar was averaged with Coke's low sodium - so Coke sat at 41,
# seven points under Poppi. Added sugar per serving now caps the score like cured meat does:
#   >= 25 g: a whole day's limit (AHA, women) in one serving        -> 15
#   >= 15 g                                                          -> 30
#   >= 10 g: the FDA "high in added sugar" line (20% DV)             -> 45
# Evidence: each extra sugar-sweetened drink a day, T2D +27%, CVD +9%, all-cause
# mortality +10% (dose-response meta-analysis, Nutrients 2021, PMC8402166). ADDED sugar
# only: 100% juice is untouched (a separate decision, see SCORING_NOTES.md).
SUGAR_DOSE_CAPS = ((25, 15), (15, 30), (10, 45))
_SWEETENER_TERMS = (
    "sugar", "cane sugar", "syrup", "corn syrup", "honey", "agave", "molasses",
    "maple syrup", "dextrose", "fructose", "sucrose", "glucose", "nectar",
    "turbinado", "demerara",
)

_CARCINOGENS = json.loads((Path(__file__).resolve().parent / "carcinogens.json").read_text())
# Product-level processing tiers that ARE processed meat in the IARC sense.
# Imitation/restructured seafood is deliberately NOT here: surimi is heavily
# processed, but it is not cured meat and the Group 1 finding does not cover
# it. Claiming otherwise would be inventing a citation.
_PROCESSED_MEAT_TIERS = {"cured or processed meat", "sliced deli meat", "hot dogs"}


def score_organic_bonus(product: dict, category: str) -> dict:
    """Only a real signal for categories where it's been checked to matter -
    see category_facts.json. Otherwise this sub-score is a flat no-op."""
    facts = CATEGORY_FACTS.get(category, {})
    if not facts.get("organic_matters"):
        return {"score": 0, "is_organic": None, "explanation": None}

    top = top_level_ingredients(product.get("ingredients") or "")
    # The bonus is for the PRIMARY ingredient being organic (the peanuts, the
    # milk), not some minor addition like organic honey in an otherwise
    # conventional product. Which word identifies that primary ingredient is
    # category-specific, so it comes from category_facts.json.
    #
    # Also checked against the product NAME, not just the ingredient list -
    # whole produce items often carry a blank or uninformative ingredients
    # field (e.g. "" for a bag of apples) even though the name itself says
    # "Wholesome Pantry Organic Gala Apples". Found 2026-09-09 while adding
    # produce categories.
    keywords = facts.get("organic_ingredient_keywords") or []
    candidates = top + [product.get("name") or ""]
    is_organic = any(
        "organic" in item.lower() and any(k in item.lower() for k in keywords)
        for item in candidates
    )

    label = keywords[0] if keywords else "ingredient"
    return {
        "score": 100 if is_organic else 0,
        "is_organic": is_organic,
        "explanation": f"organic {label}" if is_organic else None,
    }


def _in_produce_department(product: dict, category: str) -> bool:
    """True if this product is genuinely a produce-department item.

    Generalized 2026-09-12 per explicit user direction: the core "less
    processed is better" logic (this whole-food treatment included) should
    apply broadly, with category-specific tuning reserved for genuine
    exceptions - not gated behind requiring one of the ~50 hand-curated
    categories. `category_breadcrumb` is ShopRite's OWN real-time taxonomy
    signal (e.g. "/Grocery/Produce/Fresh Fruit/Apples"), present on every
    product regardless of which category collected it, and more reliable
    than either the curated `is_produce` flag (only ever set for 24
    categories) or the `aisle` field (never collected at all for the
    17,787-product full-catalog crawl, and independently flagged elsewhere
    as unreliable even where it does exist). A curated category explicitly
    marked is_produce is still honored as a fallback, in case a breadcrumb
    is ever missing on older cached data.
    """
    breadcrumb = product.get("category_breadcrumb") or ""
    if "/Produce/" in breadcrumb:
        return True
    return bool(CATEGORY_FACTS.get(category, {}).get("is_produce"))


def score_produce_freshness(product: dict, category: str) -> dict:
    """Fresh produce at this store is filed under aisle "PRODUCE DEPARTMENT";
    canned/frozen/flavored versions that slip through a name-based search
    filter (canned peaches, jalapeno-flavored cheese snacks, etc.) are filed
    under an ordinary numbered aisle instead. Found 2026-09-09 to be a far
    more reliable contamination signal than trying to enumerate every
    packaging keyword ("in syrup", "diced", brand names) up front - those
    lists kept missing real examples. Opt-in via `_in_produce_department()`
    so this never fires on packaged goods, where a numbered aisle is normal
    and means nothing about freshness.
    """
    facts = CATEGORY_FACTS.get(category, {})

    # Generalized beyond produce: any category can declare forms of itself
    # that are processed convenience versions of the whole food, via
    # `processed_form_keywords`. Eggs are the motivating non-produce case -
    # a pre-cooked peeled packaged egg was outranking organic free-range
    # fresh eggs, because being a processed PRODUCT gave it an ingredient
    # list ("Eggs") and therefore ingredient_simplicity + flagged_ingredients
    # scores that a plain carton of eggs can never earn. That's the whole-food
    # penalty inverted, and it's the same root cause as the banana-crisps bug.
    processed_kw = facts.get("processed_form_keywords") or []
    if processed_kw:
        name_l = (product.get("name") or "").lower()
        hit = next((k for k in processed_kw if k in name_l), None)
        if hit:
            return {
                "score": 25,
                "applicable": True,
                "explanation": f"processed form ('{hit}') - a convenience product, not the whole food",
            }

    if not _in_produce_department(product, category):
        return {"score": None, "applicable": False, "explanation": None}

    # Aisle alone isn't sufficient - found 2026-09-09 that dried fruit (e.g.
    # "Organic by Mariani Unsulfured Mango") is filed under "PRODUCE
    # DEPARTMENT" at this store too, same as genuinely fresh mango, and its
    # ingredient list ("Organic Dried Mangoes") makes the drying obvious.
    # Checked separately from aisle so it still fires even when aisle says
    # produce.
    #
    # CRITICAL scoping detail, learned by breaking it: these words are checked
    # against the product NAME and only the FIRST (dominant) ingredient - NOT
    # the whole ingredient blob. Searching the full blob demoted all six of
    # The Little Potato Co.'s genuinely fresh potatoes, because the seasoning
    # packet bundled with them lists "Dehydrated Onion"/"Dehydrated Garlic".
    # A dried minor ingredient says nothing about whether the actual food is
    # fresh; only the primary ingredient does.
    name = (product.get("name") or "").lower()
    ingredients = product.get("ingredients") or ""
    primary = (top_level_ingredients(ingredients)[:1] or [""])[0].lower()
    form_text = f"{name} {primary}"

    if any(w in form_text for w in ("dried", "dehydrated", "freeze-dried", "freeze dried")):
        return {
            "score": 30,
            "applicable": True,
            "explanation": "dried/dehydrated - more processed and sugar-concentrated than fresh",
        }

    # Snack forms are the nastiest case because BOTH other signals look
    # perfect: "Calbee Harvest Snaps Kids Crispy Bananas" is shelved in
    # PRODUCE DEPARTMENT and its ingredient list is literally just
    # "Bananas" - so ingredient_simplicity, flagged_ingredients and the
    # aisle check all scored it 100 and it ranked #1 in bananas at 95.8,
    # ahead of every actual banana. Puffing/crisping is real processing
    # even when nothing gets added, so it's caught by product form here.
    # Only applied to produce categories, where these words unambiguously
    # mean a snack product rather than the raw food.
    #
    # "crispy" deliberately removed from this list (found 2026-09-12 scoring
    # the full catalog): "Little Leaf Farms Baby Crispy Green Leaf" is real
    # fresh lettuce - "crispy" is a genuine textural variety descriptor for
    # leafy greens, not a snack-form signal, unlike "crisps"/"chips" as
    # nouns. The original motivating case (Calbee's banana snack) is still
    # caught via "snaps" (from its own "Harvest Snaps" brand name) - checked
    # against the real catalog before removing "crispy": no produce product
    # relied on it as the ONLY matching keyword.
    if any(w in form_text for w in ("crisps", "chips", "snaps", "puffs", "snack")):
        return {
            "score": 20,
            "applicable": True,
            "explanation": "snack form (crisps/chips/puffs) - processed, not fresh produce",
        }

    aisle = product.get("aisle")
    if not aisle:
        return {"score": None, "applicable": False, "explanation": "aisle unknown - can't verify fresh vs. processed"}

    if aisle.strip().upper() == "PRODUCE DEPARTMENT":
        # Pre-cut fresh produce: still the whole food, but cut. Checked ONLY
        # inside the produce-aisle branch, deliberately - a canned "Diced
        # Carrots" must keep the harsher aisle-mismatch 15 below rather than
        # being promoted to 70 by the word "diced".
        #
        # Why a separate, much gentler tier than processed_form_keywords (25):
        # conflating "diced fresh avocado" with "pre-cooked peeled egg patty"
        # is wrong. Cutting genuinely costs something - oxidation begins at the
        # cut surface, vitamin C and folate decline over the following days,
        # and pre-cut fruit is commonly dipped in citric/ascorbic acid to hold
        # colour - but the food itself is unchanged. A bag of cauliflower
        # florets is still cauliflower, and scoring it 25 (below canned) would
        # be a worse error than the one being fixed.
        #
        # The keyword lists are per-category and strictly evidence-based: each
        # word was confirmed against real product names in THAT category
        # first. Global lists were tried and rejected - "sliced" is
        # convenience processing for mushrooms but completely normal for bread
        # and bacon, "mini" substring-matches "CriMINI Mushrooms", and "baby"
        # would demote Baby Spinach and Baby Kale, which are varieties rather
        # than cut forms and are legitimately the best items in their
        # categories.
        pre_cut_kw = facts.get("pre_cut_keywords") or []
        if pre_cut_kw:
            name_l = (product.get("name") or "").lower()
            hit = next((k for k in pre_cut_kw if k in name_l), None)
            if hit:
                # 85, not 70. Calibrated against the renormalizer rather than
                # picked for feel: whole produce has NO ingredient list, so
                # ingredient_simplicity and flagged_ingredients are dropped for
                # it and the remaining weights are renormalized - which pushes
                # this sub-score's EFFECTIVE weight from its nominal 0.35 to
                # roughly 0.67. A penalty here therefore lands about twice as
                # hard as its face value suggests.
                #
                # At 70 the arithmetic produced a clearly wrong ranking:
                # "Fresh Cauliflower Florets" fell to 70.0, BELOW frozen
                # "Bowl & Basket Cauliflower Florets" at 71.0 - because the
                # frozen bag has an ingredient list ("Cauliflower") and so
                # collects simplicity/flagged points that fresh produce can
                # never earn. Demoting fresh below frozen is a worse error
                # than the one being corrected. 85 keeps pre-cut below whole
                # while staying comfortably above frozen and canned.
                return {
                    "score": 85,
                    "applicable": True,
                    "explanation": f"pre-cut ('{hit}') - fresh, but cut surfaces oxidize "
                                   "and lose vitamin C/folate faster than whole",
                }
        return {"score": 100, "applicable": True, "explanation": "fresh (produce department)"}

    return {
        "score": 15,
        "applicable": True,
        "explanation": f"aisle is '{aisle}', not produce department - likely canned/frozen/flavored, not fresh",
    }


# Egg husbandry tiers. Ordered most- to least-specific so that a product
# claiming several labels is scored by its STRONGEST one ("Organic Cage Free"
# is at minimum free-range in practice, since USDA Organic itself requires
# outdoor access).
#
# Why this sub-score has to exist: eggs carry NO ingredient list at all, so
# ingredient_simplicity and flagged_ingredients are both dropped for them,
# and nutrition panels are missing on over half. Before this, every egg from
# battery-caged store-brand to certified pasture-raised organic scored an
# identical 70.0 - the category was completely undifferentiated, and worse,
# the only eggs that COULD score higher were pre-cooked peeled packaged ones,
# purely because being a processed product gave them an ingredient list to
# score. Husbandry is the real quality axis for eggs, same way brand claims
# (grass-fed etc.) are for ground beef.
#
# Evidence, researched 2026-09-10: USDA legally defines "cage free" (indoor,
# uncaged, NO outdoor access) and "free range" (continuous outdoor access,
# min 2 sq ft/bird). "Pasture raised" is NOT USDA-defined but is certified by
# Humane Farm Animal Care at 108 sq ft/bird. Measured compositional
# differences favour outdoor access: Penn State found ~2.5x the omega-3 in
# pastured vs caged eggs, and an NIH-published study found ~4x the vitamin D3
# from hens kept outdoors.
#
# HONEST CAVEAT, deliberately not hidden: the Egg Nutrition Center's position
# is that overall nutritional differences are small, and the vitamin D gap
# would need 5+ eggs/day to matter clinically. So this is real measured
# evidence (better grade than peanut butter's inferred pesticide pathway,
# comparable to dairy organic's omega-3 finding) but modest in magnitude -
# which is why the weight is a tiebreaker-plus, not dominant. There is also
# an animal-welfare dimension here that is NOT what this project scores;
# the tiers above are justified on the composition evidence alone.
_EGG_HUSBANDRY_TIERS = (
    (("pasture raised", "pasture-raised"), 100, "pasture raised (most outdoor access; highest omega-3/vitamin D)"),
    (("free range", "free-range"),          75, "free range (continuous outdoor access, USDA-defined)"),
    (("cage free", "cage-free"),            50, "cage free (uncaged but indoor only - no outdoor access)"),
    # USDA Organic mandates outdoor access, so an organic carton with no other
    # housing claim is NOT conventional caged - without this tier, "Eggland's
    # Best 100% USDA Organic Certified" was being scored as battery-caged.
    # Placed below free range rather than equal to it on purpose: organic's
    # outdoor-access rule is real but its enforcement is genuinely contested
    # (screened concrete porches have counted as "outdoor"), so it earns more
    # than cage-free but shouldn't be treated as proven pasture time.
    (("organic",),                          60, "organic (USDA Organic mandates outdoor access, though enforcement is contested)"),
)


# ---------------------------------------------------------------------------
# Meat and seafood: judged on sourcing + processing, because there is nothing
# else to judge them on.
#
# 667 Meat/Seafood/Deli products score None today, every one of them for the
# same reason: a butcher-counter steak has no printed ingredient list and
# often no nutrition panel, so every other core sub-score is inapplicable.
# That is the honest answer to "is this data good enough to score", but it is
# the wrong answer to "is this good food" - a whole cut of beef and a package
# of bologna are not equally unknowable. Per user direction 2026-09-14:
# "for the meat we can still see where its sourced from and how processed it
# is and judge it that way". Same shape as the produce path, which already
# scores a loose apple with no ingredient list via produce_freshness.
#
# Department gate is exact-segment, not substring: breadcrumbs are
# "Grocery/<Department>/<Category>/<Leaf>", and a substring test for "Meat"
# wrongly catches "Grocery/Pantry/Spices, Seasonings, & Herbs/Meat
# Seasonings" (a spice rub, not meat) - the same search-contamination class
# as the "cherry" -> Coca-Cola Cherry and "corn on the cob seasoning" bugs.
# Deli is included ONLY for the two genuinely-meat subcategories; Deli also
# contains Sliced Deli Cheese, Deli Salads, Dips and Party Trays, and
# "Specialty Cheese & Meats" is mixed, so those stay out.
_DELI_MEAT_CATEGORIES = {"Sliced Deli Meat", "Packaged Deli Meat"}


def _breadcrumb_parts(product: dict) -> list[str]:
    """Split a breadcrumb into [department, category, leaf...], normalized.

    The two collection paths disagree on shape and it is easy to miss:
    the full-catalog crawl stores "Grocery/Meat/Beef/Steaks" while the
    curated per-category files store "/Grocery/Meat/Beef/Ground Beef &
    Burgers" WITH A LEADING SLASH. A naive .split("/")[1] therefore reads
    "Grocery" instead of "Meat" on every curated product, which silently
    left 9 curated ground_beef and 6 chicken_thighs products unscored while
    the identical full-catalog products scored fine. The produce gate never
    hit this because it does a substring test ("/Produce/" in breadcrumb)
    rather than indexing. Strip the slashes, then drop the "Grocery" root if
    present, so both shapes land on the same indices.
    """
    parts = [x for x in (product.get("category_breadcrumb") or "").strip("/").split("/") if x]
    if parts and parts[0] == "Grocery":
        parts = parts[1:]
    return parts


# Seafood that the store shelves under Pantry rather than Seafood. Canned
# tuna, sardines and canned salmon are 103 + 19 + 12 products whose
# wild-vs-farmed claim went completely unscored, because the department gate
# never matched. Added 2026-09-18 (Phase 7).
_SEAFOOD_PANTRY_CATEGORIES = {"Canned Tuna", "Canned Seafood", "More Canned Seafood",
                              "Sardines", "Canned Salmon"}


def _in_meat_department(product: dict) -> bool:
    parts = _breadcrumb_parts(product)
    if not parts:
        return False
    department = parts[0]
    if department in ("Meat", "Seafood"):
        return True
    if any(seg in _SEAFOOD_PANTRY_CATEGORIES for seg in parts):
        return True
    if department == "Deli" and len(parts) > 1 and parts[1] in _DELI_MEAT_CATEGORIES:
        return True
    return False


# Ordered most-processed first: a name can contain several of these words
# ("smoked sausage", "ground chuck patties") and the most processed form is
# the one that describes the product. Word-boundary matched, because naive
# substrings are wrong here in ways that matter: "ham" is inside "hamburger",
# "rib" is inside "ribbon", "cured" is inside "manicured".
_MEAT_PROCESSING_TIERS = (
    (25, "cured or processed meat", (
        "bacon", "ham", "salami", "pepperoni", "prosciutto", "sausage", "kielbasa",
        "frank", "franks", "hot dog", "hot dogs", "jerky", "bologna", "pastrami",
        "corned beef", "chorizo", "capicola", "mortadella", "smoked", "cured",
        "spam", "scrapple", "liverwurst", "bratwurst", "andouille", "soppressata",
    )),
    (55, "breaded or pre-seasoned", (
        "breaded", "nugget", "nuggets", "stuffed", "marinated", "seasoned",
        "teriyaki", "barbecue", "bbq", "ready to heat", "battered", "popcorn",
        "tempura", "kiev", "cordon bleu", "meatball", "meatballs", "meatloaf",
    )),
    (78, "ground", (
        "ground", "minced", "burger", "burgers", "patty", "patties", "chopped",
    )),
    # 88, not 100, deliberately: at 100 a whole cut is already at the ceiling,
    # so every husbandry bonus clips away to nothing and grass-fed organic
    # ribeye ties conventional USDA Choice ribeye at exactly 90 - making half
    # this sub-score (the "where is it sourced from" half the user asked for)
    # invisible on precisely the butcher-counter cuts it exists to judge.
    # Headroom is what lets sourcing actually separate them.
    (88, "whole cut", (
        "steak", "steaks", "roast", "chop", "chops", "breast", "breasts", "thigh",
        "thighs", "loin", "tenderloin", "fillet", "fillets", "filet", "filets",
        "brisket", "drumstick", "drumsticks", "wing", "wings", "shank", "cutlet",
        "cutlets", "ribs", "rib", "whole", "tail", "tails", "leg", "legs",
        "shoulder", "flank", "skirt", "rump", "round", "sirloin", "ribeye",
    )),
)

# Husbandry and feed claims that describe how the animal was actually raised.
# Deliberately EXCLUDED, and this is the whole point of the distinction:
#   - "natural" is close to meaningless on meat (USDA allows it for anything
#     minimally processed with no artificial ingredients - it says nothing
#     about how the animal lived). 51 unscored meat products carry it.
#   - "USDA Prime/Choice/Select", "Certified Angus", "Wagyu" are MARBLING and
#     breed grades - they describe fat content and tenderness, not husbandry
#     or health. 49 products say "USDA Choice" and 24 "Certified Angus";
#     treating those as a health bonus would be scoring marketing.
# Whether high marbling should be a NEGATIVE (saturated fat) is a real
# question but a contested one, and it belongs with the other open
# user-judgment calls, not decided silently here.
_SOURCING_CLAIMS = (
    (12, "organic", ("organic",)),
    (10, "grass-fed or pasture-raised", ("grass fed", "grass-fed", "grassfed", "pasture raised", "pasture-raised", "pastured")),
    (8, "wild-caught", ("wild caught", "wild-caught", "wild atlantic", "wild alaskan")),
    (6, "free-range or air-chilled", ("free range", "free-range", "air chilled", "air-chilled")),
    (5, "raised without antibiotics", ("no antibiotics", "antibiotic free", "antibiotic-free", "raised without antibiotics", "never any antibiotics")),
)
# Farm-raised fish is a genuine step down from wild-caught, but a small one -
# it is a real husbandry fact, unlike the marketing terms above.
_SOURCING_PENALTY = (-5, "farm-raised", ("farm raised", "farm-raised"))
# Bounded so sourcing can never launder processing: organic bacon is still
# cured meat, and lands at 40, not at a respectable score. Same "don't let a
# single good attribute launder a junk product" lesson as the whole-grain
# weight fix on candy-coated cereal bars.
_MAX_SOURCING_BONUS = 15


def _name_has(name: str, words) -> str | None:
    for w in words:
        if re.search(r"\b" + re.escape(w) + r"\b", name):
            return w
    return None


def _department_processing_floor(product: dict) -> tuple[int, str] | None:
    """Some subcategories ARE the processing level, whatever the name says.

    Found by measuring the first version of this sub-score against the real
    catalog: "Hillshire Farm Ultra Thin Sliced Lower Sodium Oven Roasted
    Turkey" ROSE 13.2 -> 36.9 because "roasted" matched the whole-cut tier.
    Oven-roasted sliced turkey is deli meat; "roast" there describes a
    cooking method, not an intact cut. Same for "Perdue Spicy Chicken
    Cutlets" (breaded, not a cutlet off the bone) and "Trans Ocean Classic
    Leg Style Imitation Crab" (surimi paste, matched on "leg"). The
    subcategory is the reliable signal where the name is ambiguous.
    """
    parts = _breadcrumb_parts(product)
    name = (product.get("name") or "").lower()
    if "imitation" in name or "surimi" in name:
        return 25, "imitation/restructured seafood"
    if len(parts) > 1:
        if parts[0] == "Deli" and parts[1] in _DELI_MEAT_CATEGORIES:
            return 25, "sliced deli meat"
        if parts[0] == "Meat" and parts[1] in ("Prepared & Ready to Heat", "Hot Dogs"):
            return 25 if parts[1] == "Hot Dogs" else 55, parts[1].lower()
        if parts[0] == "Seafood" and parts[1] == "Prepared Seafood":
            return 55, "prepared seafood"
    return None


def score_meat_sourcing(product: dict) -> dict:
    """Score a meat/seafood item on how processed it is and how it was raised.

    Applies to the whole Meat and Seafood departments, not just the items
    that happen to lack an ingredient list. A package of bacon that DOES
    carry an ingredient list is still cured meat, and the processing tier is
    real information about it either way.
    """
    if not _in_meat_department(product):
        return {"score": None, "applicable": False, "explanation": None}

    name = (product.get("name") or "").lower()
    if not name:
        return {"score": None, "applicable": False, "explanation": None}

    base, tier_label, hit = None, None, None
    floor = _department_processing_floor(product)
    if floor is not None:
        base, tier_label = floor
    else:
        for score, label, words in _MEAT_PROCESSING_TIERS:
            found = _name_has(name, words)
            if found:
                base, tier_label, hit = score, label, found
                break
    if base is None:
        # In the meat department but named in a way we don't recognize.
        # Assuming "whole cut, 100" on no evidence is exactly the "missing
        # data scored as good data" mistake this project keeps having to fix.
        # Lowered 85 -> 70 after measuring: at 85 this tier was RAISING
        # obviously-processed products ("Knauss Creamed Chipped Beef Topping"
        # 4.4 -> 26.5) purely because their name matched no tier keyword.
        base, tier_label, hit = 62, "unspecified cut", None

    bonus, claims = 0, []
    for value, label, words in _SOURCING_CLAIMS:
        if _name_has(name, words):
            bonus += value
            claims.append(label)
    bonus = min(bonus, _MAX_SOURCING_BONUS)
    pen_value, pen_label, pen_words = _SOURCING_PENALTY
    if _name_has(name, pen_words):
        bonus += pen_value
        claims.append(pen_label)

    score = max(0, min(100, base + bonus))
    detail = f"{tier_label}" + (f" ('{hit}')" if hit else "")
    if claims:
        detail += " - " + ", ".join(claims)
    return {
        "score": score,
        "applicable": True,
        "explanation": detail,
        "processing_tier": tier_label,
        "is_processed_meat": tier_label in _PROCESSED_MEAT_TIERS,
    }


def score_egg_husbandry(product: dict, category: str) -> dict:
    """How the hens were raised, read off the product name. Opt-in per
    category via `egg_husbandry_matters` in category_facts.json."""
    if not CATEGORY_FACTS.get(category, {}).get("egg_husbandry_matters"):
        return {"score": None, "applicable": False, "explanation": None}

    name = (product.get("name") or "").lower()
    for keywords, score, explanation in _EGG_HUSBANDRY_TIERS:
        if any(k in name for k in keywords):
            return {"score": score, "applicable": True, "explanation": explanation}

    # No claim at all. In US egg marketing an unclaimed carton means
    # conventional caged production - producers who meet a higher standard
    # advertise it, because it's what justifies the price. Treated the same
    # way as unqualified "wheat flour" meaning refined: absence of the claim
    # IS the signal, not missing data.
    return {
        "score": 25,
        "applicable": True,
        "explanation": "no housing claim on the label - conventional caged production",
    }


# NOVA is Open Food Facts' standardized 1-4 food-processing classification
# (peer-reviewed, used in public health research) - an external check on
# our own hand-tuned ingredient analysis, not a replacement for it.
_NOVA_SCORE = {1: 100, 2: 80, 3: 50, 4: 15}
_NOVA_LABEL = {
    1: "unprocessed/minimally processed",
    2: "processed culinary ingredients",
    3: "processed food",
    4: "ultra-processed food",
}


def score_external_processing(off_product: dict | None) -> dict:
    """off_product is this item's Open Food Facts record, or None if not
    found there.

    A missing NOVA grade makes this sub-score NOT APPLICABLE - it is dropped
    and the remaining weights renormalize. It used to return a "neutral" 70,
    with the stated intent that missing data shouldn't swing the score. That
    intent was right and the implementation was backwards: including a 70 at
    weight 0.17 IS a swing, and a downward one for anything genuinely good.
    3,696 scored products (25% of the catalog) have no NOVA grade, so a
    quarter of everything was carrying a fabricated number for nearly a fifth
    of its score. Poland Spring water scored 83 while hitting 100 on
    ingredient simplicity, flagged ingredients AND nutrition - nothing could
    reach the top of the scale.

    This is the project's oldest bug class one more time ("missing data must
    not be scored as data"), just inverted into a penalty instead of a
    reward. Per user direction 2026-09-15: NOVA should absolutely count when
    it exists; not having one should cost nothing.

    Dropping it cannot resurrect the 2026-09-11 variety-pack bug, where a
    product with NO core signal got a score built purely from this default:
    compute_score() only includes this sub-score at all once some core
    sub-score already applies.
    """
    nova = (off_product or {}).get("nova_group")
    if nova not in _NOVA_SCORE:
        return {"score": None, "applicable": False, "nova_group": None, "explanation": None}
    # Only NOVA 4 (ultra-processed) counts - owner decision 2026-10-03 ("option C"). Groups 1-3
    # are already judged by our own ingredient analysis, and a grade being present or absent was
    # swinging near-identical foods: NOVA puts ALL cheese in group 3, so BelGioioso mozzarella
    # (graded) lost ~7 points to Bowl & Basket mozzarella (no grade) for nothing about the cheese.
    # OFF also mis-grades some ultra-processed products as 1-2 (PediaSure, a bottled dressing),
    # which this stops inflating. What NOVA is uniquely good at - flagging ultra-processing -
    # still counts in full.
    if nova != 4:
        return {"score": None, "applicable": False, "nova_group": nova, "explanation": None}

    inferred = (off_product or {}).get("nova_inferred")
    if inferred:
        source = (f"inferred from {inferred['from_siblings']} same-brand products "
                  f"in this category, {int(inferred['agreement'] * 100)}% agreeing")
    else:
        source = "via Open Food Facts"
    return {
        "score": _NOVA_SCORE[nova],
        "applicable": True,
        "nova_group": nova,
        "nova_inferred": bool(inferred),
        "explanation": f"NOVA {nova} ({_NOVA_LABEL[nova]}, {source})",
    }


# A produce-aisle item whose NAME tells you it contains something other than
# produce. "An avocado contains avocado" is a fact we can assert; "a Chopped
# Kit Bacon Thousand Island Salad contains lettuce" is not - it contains
# dressing, bacon and cheese, none of which are in the produce aisle.
#
# Found 2026-09-15 by opening the app and reading a card: "Bowl & Basket
# Vegetable Platter with Ranch Dip" scored a perfect 100.0 explained as
# "whole food - nothing added", and Fresh Express chopped kits scored 85-95
# the same way. All of them carry no ingredient list, so the whole-produce
# escape hatch fired and handed them 100 for simplicity AND 100 for flagged
# ingredients. This is the banana-crisps / peeled-egg failure once more: a
# processed product collecting the whole food's benefit of the doubt.
#
# Matched as whole words against the name. Bare greens must NOT match -
# "Spring Mix", "Italian Blend", "Coleslaw Blend" and "Arugula" are genuinely
# just leaves and correctly score 100.
_NOT_JUST_PRODUCE = (
    "kit", "kits", "dip", "dressing", "crouton", "croutons", "bacon", "cheese",
    "cheddar", "parmesan", "feta", "ranch", "caesar", "thousand island",
    "vinaigrette", "platter", "tray", "glaze", "candied", "praline", "seasoned",
    "marinated", "stuffed", "wrap", "sandwich", "dessert", "yogurt", "granola",
    "chocolate", "caramel",
)


def _produce_item_has_non_produce_parts(product: dict) -> bool:
    name = (product.get("name") or "").lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", name) for w in _NOT_JUST_PRODUCE)

def _is_whole_fresh_produce(product: dict, category: str) -> bool:
    """True for an unpackaged whole food sitting in the produce department
    with no printed ingredient list.

    This is the narrow escape hatch for the structural bias that kept
    reappearing in this project under different disguises. A loose avocado has
    NO label, so ingredient_simplicity and flagged_ingredients are both
    dropped for it and it gets judged on produce_freshness alone. A tub of
    diced avocado, being a packaged product, carries the list "Hass Avocados"
    and therefore collects 100 for simplicity, 100 for flagged and a nutrition
    panel too - four favourable sub-scores against the whole fruit's one. The
    processed item ends up with MORE evidence of being good, purely by virtue
    of being processed, and outranks the thing it was made from.

    Treating the absence as unknown is wrong here, and this is the one place
    where saying so does not violate the project's "missing data must never
    score as good data" rule: for a whole food in the produce aisle the
    ingredient list is not unknown, it is the food. An avocado contains
    avocado. That is a fact we can assert, not a gap we are papering over.

    Deliberately narrow. Requires both of:
      - the product is genuinely a produce-department item, per
        `_in_produce_department()` (breadcrumb-based, generalized 2026-09-12
        beyond the ~24 curated produce categories - see that function)
      - there is genuinely no ingredient list to read instead
    A store-baked bread loaf with no label stays unscored, as it must - bread
    isn't a produce-department item, and an unlabelled loaf really could
    contain anything.
    """
    if not _in_produce_department(product, category):
        return False
    if _produce_item_has_non_produce_parts(product):
        # Not whole produce. It falls through to the ordinary "no ingredient
        # list" path and goes UNSCORED on ingredients, which is the honest
        # answer - we genuinely don't know what is in the dressing packet.
        return False
    return not (product.get("ingredients") or "").strip()


def score_ingredient_simplicity(product: dict, category: str = "") -> dict:
    raw = product.get("ingredients") or ""
    top = top_level_ingredients(raw)
    flat = flatten_all_mentions(raw)
    top_count = len(top)
    flat_count = len(flat)
    nested_extra = max(0, flat_count - top_count)

    # No ingredient list at all is missing data, NOT a clean product. Without
    # this guard an unlabeled item scores a perfect 100 for "0 ingredients"
    # and can top the rankings (a store-baked loaf did exactly that).
    if top_count == 0:
        if _is_whole_fresh_produce(product, category):
            return {
                "score": 100,
                "applicable": True,
                "top_level_count": 1,
                "flattened_count": 1,
                "explanation": "whole food - the only ingredient is the food itself",
            }
        return {
            "score": None,
            "applicable": False,
            "top_level_count": 0,
            "flattened_count": 0,
            "explanation": "no ingredient list available",
        }

    penalty, first = 0, True
    for item in top:
        t = item.strip().lower()
        core = _SIMPLE_QUALIFIERS.sub("", t).strip(" *.")
        if t in _NEUTRAL_INGREDIENTS or core in _NEUTRAL_INGREDIENTS:
            continue
        if first:                      # the main ingredient itself is free, as it always was
            first = False
            continue
        penalty += (KITCHEN_INGREDIENT_COST
                    if _KITCHEN_INGREDIENT.search(core) and not _NOT_KITCHEN.search(core)
                    else OTHER_INGREDIENT_COST)
    score = 100 - penalty - nested_extra * 2
    score = max(0, min(100, score))

    return {
        "score": score,
        "applicable": True,
        "top_level_count": top_count,
        "flattened_count": flat_count,
        "explanation": f"{top_count} ingredient{'s' if top_count != 1 else ''}"
        + (f" ({flat_count} total incl. sub-ingredients)" if nested_extra else ""),
    }


def score_flagged_ingredients(product: dict, category: str = "") -> dict:
    raw = (product.get("ingredients") or "").lower()
    # Words that CONTAIN a flag term without being it (audit 2026-10-02): "sugar snap
    # peas" are not added sugar (plain frozen snap peas scored 40) and "honeydew" is not
    # honey. And "citric acid (preservative)" or "tocopherols (preservative)" names an
    # antioxidant, not a preservative additive - but the bare word must keep catching the
    # real ones the term list lacks (potassium benzoate, sulfites, EDTA, parabens).
    raw = re.sub(r"sugar snap|honeydew", "pea", raw)
    raw = re.sub(r"(citric acid|ascorbic acid|tocopherols?|vitamin e|rosemary extract)\s*[\(\[][^\)\]]*preservative[^\)\]]*[\)\]]", r"\1", raw)
    if not raw.strip():
        if _is_whole_fresh_produce(product, category):
            # Loose fruit and veg in the produce aisle has nothing added to
            # it - no sweetener, no oil, no preservative. That is a genuine
            # observation about the item, not an optimistic default.
            return {
                "score": 100,
                "applicable": True,
                "matched": [],
                "explanation": "whole food - nothing added",
            }
        # Absent list - can't claim "no flagged ingredients".
        return {"score": None, "applicable": False, "matched": [], "explanation": "no ingredient list available"}
    # Match space-insensitively as well as literally. Labels and OCR drop or
    # add spaces freely: Twizzlers' entire ingredient field is the single word
    # "cornsyrup", which never matched the term "corn syrup", so a bag of
    # candy scored 100 for "no flagged ingredients". 959 products were missing
    # a flag for exactly this reason - mostly "cornstarch" vs "corn starch".
    # Found 2026-09-15 while chasing the user's NOVA question.
    squished = re.sub(r"\s+", "", raw)
    matched = []
    penalty = 0
    max_severity = 0
    for key, cat in FLAGGED_CATEGORIES.items():
        if any(term in raw or re.sub(r"\s+", "", term) in squished for term in cat["terms"]):
            matched.append(cat["label"])
            penalty += cat["severity"]
            max_severity = max(max_severity, cat["severity"])

    score = max(0, 100 - penalty * 12)
    explanation = "no flagged ingredients" if not matched else ", ".join(matched)

    return {"score": score, "applicable": True, "matched": matched, "max_severity": max_severity, "explanation": explanation}


def _serving_grams(product: dict) -> float | None:
    """Serving weight in grams, from either source's own format.

    The two data sources disagree on shape, and only the ShopRite form was
    ever handled - found 2026-09-12 before enabling a fat-density baseline on
    a full-catalog category, which would have thrown AttributeError on every
    Open Food Facts product:
      - ShopRite product pages: {"size": 33, "type": "gram", ...}
      - Open Food Facts:        "126g" / "229.99999999999997g" / "1 Cup"

    A serving given only as "1 Cup" has no weight to divide by, so it
    correctly yields None (caller drops the sub-score) rather than guessing a
    gram value - same "missing data is not good data" rule used everywhere
    else here.
    """
    raw = product.get("serving_size")
    if isinstance(raw, dict):
        return raw.get("size")
    if isinstance(raw, str):
        m = re.search(r"([\d.]+)\s*g\b", raw, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def score_whole_food_processing(product: dict, category: str) -> dict:
    """Detects fat mechanically pressed out of a naturally fatty whole food
    (e.g. powdered peanut butter loses most of the monounsaturated fat and
    vitamin E of whole peanuts, while its ingredient list still reads clean).

    This only means something for a food with a known natural fat density,
    so it's opt-in per category via `whole_food_fat_density_baseline` in
    category_facts.json. For any category without one it returns
    applicable=False and is dropped from the weighting entirely, rather
    than silently handing every product a free 100.
    """
    baseline = CATEGORY_FACTS.get(category, {}).get("whole_food_fat_density_baseline")
    if not baseline:
        return {"score": None, "applicable": False, "fat_density_pct": None, "explanation": None}

    nutrition = product.get("nutrition") or {}
    fat_entry = nutrition.get("total Fat")
    # Note: 0g fat is a real measurement, not missing data - check for None
    # explicitly rather than using a falsy check.
    fat_g = fat_entry.get("size") if isinstance(fat_entry, dict) else None
    serving_g = _serving_grams(product)

    if fat_g is None or not serving_g:
        return {"score": None, "applicable": False, "fat_density_pct": None, "explanation": "fat data unavailable"}

    fat_density = fat_g / serving_g
    deficit = max(0.0, (baseline - fat_density) / baseline)
    score = round(100 * (1 - deficit))

    pct = round(fat_density * 100)
    baseline_pct = round(baseline * 100)
    explanation = (
        f"{pct}% fat by weight (natural is ~{baseline_pct}%) - oil appears mechanically removed"
        if deficit > 0.15
        else f"{pct}% fat by weight, close to natural"
    )

    return {"score": score, "applicable": True, "fat_density_pct": pct, "explanation": explanation}


_GRAIN_WORDS = ("flour", "grain", "wheat", "oat", "rye", "barley", "rice", "corn", "spelt", "millet")
_WHOLE_MARKERS = ("whole", "sprouted", "cracked", "stone ground", "stone-ground")
# In US labeling, an unqualified "wheat flour" or "enriched flour" IS refined
# white flour - only "whole wheat"/"whole grain" means the bran and germ are
# still there. Enrichment (niacin/folic acid/reduced iron added back) is
# itself the tell that they were stripped out.
_REFINED_MARKERS = ("enriched", "bleached", "unbleached", "white flour", "semolina", "durum")

# "flour" is in _GRAIN_WORDS, which wrongly swept in legume and nut flours -
# found 2026-09-10 when "Barilla Red Lentil Penne" and "Barilla Chickpea
# Penne" were both being reported as "refined flour" and penalized as if
# they were white pasta. A lentil isn't a refined grain; the whole/refined
# distinction is about stripping bran and germ off a cereal grain and has no
# meaning for a legume. These are filtered out before the grain rule runs.
# Note this only excludes them when a legume flour is the ONLY flour - e.g.
# Barilla Protein+ still scores as refined because its first ingredient is
# genuinely semolina, with legume flour further down.
_NON_GRAIN_FLOURS = (
    "lentil", "chickpea", "garbanzo", "black bean", "edamame", "soy",
    "almond", "coconut", "cassava", "tapioca", "potato flour",
)

# Some categories name their whole grains differently and need EXTRA markers
# beyond the generic ones above - supplied per category as
# `whole_grain_markers` in category_facts.json. Rice is the motivating case:
# "brown rice" IS whole grain by definition (bran and germ intact) but often
# never says the word "whole" on the label - real examples from this store's
# data include "Long Grain Brown Rice" and "Brown Basmati Rice", both of
# which the generic markers alone would misjudge as refined.
#
# Deliberately NOT added to the global list: "brown" is only trustworthy for
# rice. On bread it's a classic trap - "brown bread" is frequently just white
# flour colored with caramel/molasses, so crediting it as whole grain there
# would be actively wrong.
def _whole_markers_for(category: str) -> tuple:
    extra = CATEGORY_FACTS.get(category, {}).get("whole_grain_markers") or []
    return _WHOLE_MARKERS + tuple(m.lower() for m in extra)


def _refined_markers_for(category: str) -> tuple:
    """Symmetric with _whole_markers_for. Breakfast cereals are the case that
    needs this: "degerminated" corn literally means the germ was removed, and
    "milled corn" / "corn meal" are refined, but none of those words appear in
    the generic refined list, which was written for bread flour."""
    extra = CATEGORY_FACTS.get(category, {}).get("refined_grain_markers") or []
    return _REFINED_MARKERS + tuple(m.lower() for m in extra)


def score_whole_grain(product: dict, category: str) -> dict:
    """Whole grain vs. refined, judged by the FIRST grain in the list (the
    dominant one). Opt-in per category via `whole_grain_matters`."""
    if not CATEGORY_FACTS.get(category, {}).get("whole_grain_matters"):
        return {"score": None, "applicable": False, "explanation": None}

    whole_markers = _whole_markers_for(category)
    # "flour" reads wrong for rice/pasta-style categories, so the noun used
    # in explanations is category-configurable and just defaults to flour.
    grain_noun = CATEGORY_FACTS.get(category, {}).get("whole_grain_noun", "flour")

    top = top_level_ingredients(product.get("ingredients") or "")
    grains = [
        i.lower() for i in top
        if any(w in i.lower() for w in _GRAIN_WORDS)
        and not any(w in i.lower() for w in _NON_GRAIN_FLOURS)
    ]
    if not grains:
        # Either no grain at all, or the only "flour" present is a legume/nut
        # flour. Refined-vs-whole is a grain concept and simply doesn't apply
        # to those, so drop the sub-score (weights get renormalized) rather
        # than judge them by a rule that was never about them.
        return {"score": None, "applicable": False, "explanation": None}

    primary = grains[0]
    primary_is_whole = any(m in primary for m in whole_markers)
    any_whole = any(any(m in g for m in whole_markers) for g in grains)
    primary_is_refined = any(m in primary for m in _refined_markers_for(category)) and not primary_is_whole

    if primary_is_whole:
        return {"score": 100, "applicable": True, "explanation": f"whole grain first ({primary[:38]})"}
    if any_whole:
        return {"score": 55, "applicable": True, "explanation": f"refined {grain_noun} first, some whole grain further down"}
    if primary_is_refined:
        return {"score": 20, "applicable": True, "explanation": f"refined {grain_noun} ({primary[:38]})"}
    # Unqualified "wheat flour" is refined in US labeling.
    return {"score": 25, "applicable": True, "explanation": f"refined {grain_noun} ({primary[:38]})"}


def score_nutrition(product: dict) -> dict:
    """Scores only the nutrients actually present on the label.

    Critically: a MISSING value is not treated as zero. Some ShopRite
    products carry an abbreviated panel (calories/sodium/protein only),
    and defaulting the absent fields to 0 previously made the scorer
    claim things like "no added sugar" for Jif - whose second ingredient
    is sugar. Absent nutrients are excluded from the average and reported
    as "no data" instead.
    """
    nutrition = product.get("nutrition") or {}

    def size(key):
        entry = nutrition.get(key)
        if not isinstance(entry, dict):
            return None
        return entry.get("size")  # may legitimately be 0

    added_sugar = size("added Sugars")
    sodium = size("sodium")
    sat_fat = size("saturated Fat")

    parts = []   # (score, fact_text) for nutrients we actually have
    missing = []

    if added_sugar is None:
        missing.append("added sugar")
    else:
        parts.append((
            100 if added_sugar == 0 else max(0, 100 - added_sugar * 15),
            "no added sugar" if added_sugar == 0 else f"{added_sugar:g}g added sugar",
        ))

    if sodium is None:
        missing.append("sodium")
    else:
        # 140mg/serving or less is the FDA's own "low sodium" labeling
        # threshold - don't penalize normal light salting.
        parts.append((
            100 if sodium <= 140 else max(0, 100 - (sodium - 140) / 3),
            f"{sodium:g}mg sodium",
        ))

    if sat_fat is None:
        missing.append("saturated fat")
    else:
        parts.append((max(0, 100 - sat_fat * 15), f"{sat_fat:g}g saturated fat"))

    if not parts:
        return {
            "score": None,
            "applicable": False,
            "added_sugar_g": added_sugar,
            "sodium_mg": sodium,
            "saturated_fat_g": sat_fat,
            "explanation": "no nutrition data",
        }

    score = round(sum(s for s, _ in parts) / len(parts))
    facts = [text for _, text in parts]
    if missing:
        facts.append(f"no data on {'/'.join(missing)}")

    return {
        "score": score,
        "applicable": True,
        "added_sugar_g": added_sugar,
        "sodium_mg": sodium,
        "saturated_fat_g": sat_fat,
        "explanation": ", ".join(facts),
    }


# Cured meats that a shop files outside the Meat department entirely. Found by
# looking at the app: "Hormel Black Label Real Chopped Bacon" and "Oscar Mayer
# Real Bacon Bits" live under Pantry/Salad Toppings/Bacon Bits, and "Jack
# Link's Bacon Jerky" under Snacks/Jerky & Meat Snacks - so the
# department-based tier never fired and none of them carried the Group 1
# warning, even though bacon bits are exactly what the classification covers.
_CURED_MEAT_WORDS = (
    "bacon", "ham", "salami", "pepperoni", "prosciutto", "sausage", "kielbasa",
    "jerky", "bologna", "pastrami", "corned beef", "chorizo", "capicola",
    "mortadella", "soppressata", "hot dog", "frankfurter", "pancetta", "speck",
)


# IARC's Group 1 processed-meat finding (Monographs Vol. 114) is about MEAT -
# mammalian muscle. FISH IS NOT IN IT. The processing tier still fires on
# smoked fish, correctly, because "Acme Smoked Fish Herring in Wine Sauce" is
# genuinely a cured product - but attaching the Group 1 citation to it would
# be a MISCITATION, and a warning that misquotes its own source is worse than
# no warning. (Chinese-style salted fish is separately Group 1, but that is a
# specific food, not smoked salmon in general.) Nitrites are still flagged on
# these products where present, which is accurate and is the useful signal.
_FISH_WORDS = ("salmon", "herring", "tuna", "cod", "haddock", "mackerel", "trout",
               "sardine", "anchovy", "whitefish", "lox", "fish", "shrimp", "crab",
               "lobster", "scallop", "clam", "oyster", "squid", "octopus", "tilapia")


def _is_seafood(product: dict) -> bool:
    parts = _breadcrumb_parts(product)
    if parts and parts[0] == "Seafood":
        return True
    first = re.split(r"[,(]", (product.get("ingredients") or "").strip().lower())[0]
    return any(re.search(r"\b" + w + r"\b", first) for w in _FISH_WORDS)

def _is_cured_meat_product(product: dict) -> bool:
    """True when the product IS cured meat, rather than merely containing some.

    The test is the FIRST ingredient, which is the honest dividing line: a jar
    of bacon bits lists "Bacon (cured with water, salt, ... sodium nitrite)"
    first and is processed meat; a "Bacon Caesar Salad" or "Smoky Bacon
    Cheddar" lists lettuce or milk first and is a salad or a cheese that
    happens to contain (or merely imitate) some. Labelling the salad a Group 1
    carcinogen would be the kind of overstatement that makes a warning
    worthless - people stop reading them.
    """
    # Subcategories that are cured meat by definition, whatever aisle the shop
    # files them in.
    parts = _breadcrumb_parts(product)
    if any(seg in ("Jerky & Meat Snacks", "Bacon Bits") for seg in parts):
        return True

    ingredients = (product.get("ingredients") or "").strip().lower()
    if not ingredients:
        return False
    first = re.split(r"[,(]", ingredients)[0].strip()
    if not first or len(first) > 60:
        return False
    # "pork cured with: water" - the meat word is generic ("pork"), but the
    # CURING is stated outright, which is the thing the classification is
    # about. Jack Link's Bacon Jerky reads exactly like this and was slipping
    # through a meat-noun-only test.
    if re.search(r"\bcured\b", first):
        return True
    return any(re.search(r"\b" + w + r"\b", first) for w in _CURED_MEAT_WORDS)

# Nutrition banners. These do NOT affect the score - per user direction
# 2026-09-15, ingredients stay the basis of the score and nutrition is
# surfaced as information instead ("for now maybe we can include a banner
# with a note that says 'high in fats' or 'calorie dense'"). A later
# nutrition tab can build on the same function.
#
# Thresholds are the FDA's own "high in" definition - 20% or more of the
# Daily Value per serving - rather than numbers invented here, so "high in
# sodium" means the same thing it means on a nutrition label. DVs used:
# sodium 2,300mg, saturated fat 20g, added sugars 50g, total fat 78g.
# Front-of-pack warning labels in Chile and Mexico work the same way.
_DAILY_VALUES = {
    "sodium": (2300, "mg", "sodium"),
    "saturated Fat": (20, "g", "saturated fat"),
    "added Sugars": (50, "g", "added sugar"),
    "total Fat": (78, "g", "fat"),
}
_HIGH_IN_FRACTION = 0.20
# "Calorie dense" is not an FDA term. 400 kcal/100g is the common
# energy-density cutoff used in nutrient-profiling work; it needs BOTH a
# calorie figure and a real serving weight, so it is simply absent when
# either is missing rather than guessed at.
_CALORIE_DENSE_PER_100G = 400


def nutrition_flags(product: dict) -> list[dict]:
    """Informational "high in ..." banners. Never affects total_score."""
    nutrition = product.get("nutrition") or {}

    def size(key):
        entry = nutrition.get(key)
        return entry.get("size") if isinstance(entry, dict) else None

    flags = []
    for key, (dv, unit, label) in _DAILY_VALUES.items():
        value = size(key)
        if value is None or value <= 0:
            continue
        pct = value / dv
        if pct >= _HIGH_IN_FRACTION:
            flags.append({
                "id": f"high_{label.replace(' ', '_')}",
                "label": f"High in {label}",
                "detail": f"{value:g}{unit} per serving, {round(pct * 100)}% of the daily value",
                "basis": "FDA 'high in' threshold: 20% or more of the Daily Value per serving",
            })

    calories = size("calories")
    grams = _serving_grams(product)
    if calories and grams and grams > 0:
        per100 = calories / grams * 100
        if per100 >= _CALORIE_DENSE_PER_100G:
            flags.append({
                "id": "calorie_dense",
                "label": "Calorie dense",
                "detail": f"{round(per100)} calories per 100g",
                "basis": "400 kcal/100g, the usual energy-density cutoff in nutrient profiling",
            })

    # Most severe first, so a card showing only one shows the worst.
    order = {"high_sodium": 0, "high_saturated_fat": 1, "high_added_sugar": 2,
             "calorie_dense": 3, "high_fat": 4}
    flags.sort(key=lambda f: order.get(f["id"], 9))
    return flags

def _primary_sweetener(product: dict) -> str | None:
    """The sweetener, when it is the product's FIRST ingredient.

    First-ingredient means largest by weight, so the product is mostly sugar.
    Whole fruit is not caught: dates, raisins and dried mango list themselves
    first, not a sweetener.
    """
    ingredients = (product.get("ingredients") or "").strip().lower()
    if not ingredients:
        return None
    first = ingredients.split(",")[0].strip()
    first = re.sub(r"sugar snap", "snap", first)     # snap peas are not sugar (audit 2026-10-02)
    if not first or len(first) > 60:
        return None
    return next((t for t in _SWEETENER_TERMS
                 if re.search(r"\b" + re.escape(t) + r"\b", first)), None)

def _sugar_dose_cap(product: dict) -> int | None:
    """The ceiling for this much ADDED sugar in one serving (SUGAR_DOSE_CAPS), or None."""
    nutrition = product.get("nutrition") or {}
    entry = nutrition.get("added Sugars")
    grams = entry.get("size") if isinstance(entry, dict) else None
    if not isinstance(grams, (int, float)):
        # Some panels carry only TOTAL sugars. For sweetened water - a drink or an ice
        # whose list is "water, <sweetener>, ..." - every gram of it is added, so the
        # total is the added figure (Stewart's sodas, Rosati ices). Anything else (milk,
        # fruit) has natural sugar in the total, and is left alone.
        top = [t.strip() for t in (product.get("ingredients") or "").lower().split(",")]
        total = nutrition.get("total Sugars")
        if (len(top) >= 2 and re.fullmatch(r"(carbonated |filtered |purified |sparkling )?water", top[0])
                and any(re.search(r"\b" + re.escape(t) + r"\b", top[1]) for t in _SWEETENER_TERMS)
                and isinstance(total, dict) and isinstance(total.get("size"), (int, float))):
            grams = total["size"]
        else:
            return None
    return next((cap for limit, cap in SUGAR_DOSE_CAPS if grams >= limit), None)


def _primary_seed_oil(product: dict) -> str | None:
    """The seed oil, when it is the product's FIRST ingredient."""
    ingredients = (product.get("ingredients") or "").strip().lower()
    if not ingredients:
        return None
    # Split on COMMA ONLY, deliberately - not on "(" as the cured-meat check
    # does. Spectrum Organic Canola Oil lists "100% MECHANICALLY (EXPELLER)
    # PRESSED REFINED ORGANIC CANOLA OIL.", and splitting at the bracket left
    # "100% mechanically", so a pure bottle of canola oil escaped the cap and
    # sat at 84.3. Comma-splitting keeps the whole first ingredient intact and
    # still correctly skips "White Tuna, Soybean Oil" and "Oysters, cottonseed
    # oil, salt", where the oil is genuinely secondary.
    first = ingredients.split(",")[0].strip()
    if not first or len(first) > 90:
        return None
    terms = (FLAGGED_CATEGORIES.get("seed_oil") or {}).get("terms") or []
    return next((t for t in terms if t in first), None)


def ingredient_banners(product: dict) -> list[dict]:
    """Ingredient-based banners, shown alongside the nutrition ones."""
    banners = []
    oil = _primary_seed_oil(product)
    if oil:
        banners.append({
            "id": "seed_oil",
            "label": "Seed oil",
            "detail": f"{oil} is the main ingredient",
            "basis": "Industrially refined seed oils. Olive, avocado and coconut are not counted.",
        })
    elif any(t in (product.get("ingredients") or "").lower()
             for t in ((FLAGGED_CATEGORIES.get("seed_oil") or {}).get("terms") or [])):
        banners.append({
            "id": "contains_seed_oil",
            "label": "Contains seed oil",
            "detail": "listed in the ingredients",
            "basis": "Industrially refined seed oils. Olive, avocado and coconut are not counted.",
        })
    return banners

def detect_carcinogens(product: dict, meat: dict | None = None) -> list[dict]:
    """Ingredients or product classes with a real, citable carcinogenicity
    classification. Returns a list so the UI can show WHAT and WHO SAYS SO,
    rather than an unexplained symbol.

    Levels are kept separate on purpose. IARC Group 1 ("known") and Group 2B
    ("possible") are very different claims, and flattening them into one
    scary badge would misinform - the point of the warning is to let someone
    judge, not to alarm them uniformly.
    """
    found = []
    is_processed_meat = (
        (meat and meat.get("processing_tier") in _PROCESSED_MEAT_TIERS)
        or _is_cured_meat_product(product)
    ) and not _is_seafood(product)
    if is_processed_meat:
        for pc in _CARCINOGENS["product_classes"]:
            if pc["id"] == "processed_meat":
                entry = {k: pc[k] for k in ("id", "level", "label", "classification", "source", "note")}
                # A sausage ravioli or a chorizo breakfast bowl CONTAINS
                # processed meat as its main ingredient; it is not itself a
                # cut of processed meat. Say which, rather than letting the
                # badge overstate what the product is.
                if not _in_meat_department(product):
                    entry["label"] = "Contains processed meat"
                found.append(entry)

    ingredients = (product.get("ingredients") or "").lower()
    if ingredients:
        for entry in _CARCINOGENS["ingredients"]:
            hit = next((t for t in entry["terms"]
                        if re.search(r"\b" + re.escape(t) + r"\b", ingredients)), None)
            if hit:
                item = {k: entry[k] for k in ("id", "level", "label", "classification", "source", "note")}
                item["matched"] = hit
                found.append(item)

    rank = {k: v["rank"] for k, v in _CARCINOGENS["levels"].items()}
    found.sort(key=lambda x: rank.get(x["level"], 9))
    return found

# Label footnotes such as "*an ingredient not found in regular milk" (32 products, found by the
# 2026-10-04 score audit) were being counted as one more ingredient. The marked ingredients
# themselves (lactase enzyme, DHA, the calcium and vitamin D in orange juice) stay.
_FOOTNOTE = re.compile(r"[,.;]?\s*[*\u2020\u2021]*\s*(an?\s+)?ingredients?\s+not\s+(found|present)\s+in\s+(regular|ordinary)\s+[a-z ]+?(?=[,.;)]|$)", re.I)


def _strip_footnotes(product: dict) -> dict:
    raw = product.get("ingredients") or ""
    if not _FOOTNOTE.search(raw):
        return product
    return {**product, "ingredients": re.sub(r"\s{2,}", " ", _FOOTNOTE.sub("", raw)).strip(" ,;")}


_ZERO_SUGAR_NAME = re.compile(r"zero sugar|sugar[- ]free|no sugar added|unsweetened", re.I)


def _drop_impossible_added_sugar(product: dict) -> dict:
    """An added-sugar figure that can't be true is treated as unknown rather than scored. From the
    2026-10-04 audit: Mountain Dew Zero Sugar carried 44 g added sugar, La Choy teriyaki 19 g added
    against 1 g total. Impossible = more added than total sugar, or 1 g+ on a product named zero
    sugar / sugar free / no sugar added / unsweetened. 13 products."""
    n = product.get("nutrition") or {}
    added = (n.get("added Sugars") or {}).get("size")
    total = (n.get("total Sugars") or {}).get("size")
    if not isinstance(added, (int, float)) or added <= 0:
        return product
    impossible = (isinstance(total, (int, float)) and added > total + 0.5) or \
        (added >= 1 and _ZERO_SUGAR_NAME.search(product.get("name") or ""))
    if not impossible:
        return product
    return {**product, "nutrition": {k: v for k, v in n.items() if k != "added Sugars"}}


def compute_score(product: dict, profile: dict, category: str = "peanut_butter", off_product: dict | None = None) -> dict:
    product = _drop_impossible_added_sugar(_strip_footnotes(product))
    simplicity = score_ingredient_simplicity(product, category)
    flagged = score_flagged_ingredients(product, category)
    nutrition = score_nutrition(product)
    processing = score_whole_food_processing(product, category)
    organic = score_organic_bonus(product, category)
    external = score_external_processing(off_product)
    whole_grain = score_whole_grain(product, category)
    freshness = score_produce_freshness(product, category)
    husbandry = score_egg_husbandry(product, category)
    meat = score_meat_sourcing(product)

    weights = profile["weights"]
    # The organic weight is a fact about this food category (how strong is
    # the pesticide-exposure evidence), not a health-philosophy choice - it
    # lives in category_facts.json, not the profile, so every profile
    # (default, future "bodybuilding", etc.) inherits the same researched
    # value instead of each guessing its own.
    organic_weight = CATEGORY_FACTS.get(category, {}).get("organic_weight", 0)

    # Sub-scores that don't apply to this category (e.g. the peanut-specific
    # fat-density check on yogurt) are dropped and the remaining weights
    # renormalized - otherwise the category's ceiling would silently fall
    # below 100 and scores wouldn't be comparable across categories.
    # Record the weight actually applied to each sub-score. Diet profiles
    # re-combine these in the browser (proto_shared.js applyProfile) rather
    # than the catalog being re-scored once per profile: the sub-scores are
    # profile-independent facts about the product, only their weighting is a
    # health-philosophy choice. Without the weight stored, the client would
    # have to guess at the category-specific ones (organic, whole-grain,
    # meat sourcing), which vary per category.
    def _use(sub, weight):
        sub["weight"] = weight
        components.append((sub["score"], weight))

    components = []
    has_core_signal = False
    if simplicity.get("applicable"):
        _use(simplicity, weights["ingredient_simplicity"]); has_core_signal = True
    if flagged.get("applicable"):
        _use(flagged, weights["flagged_ingredients"]); has_core_signal = True
    if nutrition.get("applicable"):
        _use(nutrition, weights["nutrition"]); has_core_signal = True
    if processing.get("applicable"):
        _use(processing, weights["whole_food_processing"]); has_core_signal = True
    if whole_grain.get("applicable"):
        _use(whole_grain, CATEGORY_FACTS.get(category, {}).get("whole_grain_weight", 0.20)); has_core_signal = True
    if freshness.get("applicable"):
        # Same weight for every produce category - the aisle-mismatch signal
        # is equally diagnostic regardless of which fruit/vegetable it is,
        # unlike organic weight which varies with how strong the pesticide
        # evidence is per food.
        _use(freshness, CATEGORY_FACTS.get(category, {}).get("produce_freshness_weight", 0.35)); has_core_signal = True
    if husbandry.get("applicable"):
        _use(husbandry, CATEGORY_FACTS.get(category, {}).get("egg_husbandry_weight", 0.30)); has_core_signal = True
    if meat.get("applicable"):
        # Deliberately ASYMMETRIC, and this is the crux of the sub-score.
        # Processing-tier-from-the-name is a PROXY for how processed a meat
        # is. When there is no ingredient list at all (the butcher counter -
        # the case this exists for) it is the best evidence available and
        # carries a produce_freshness-sized weight. When a real ingredient
        # list EXISTS, the proxy must defer to it: measured on the first
        # version, a flat 0.32 let heavily-processed products launder their
        # shape into a much better score (Hillshire sliced turkey 13.2 ->
        # 36.9, Knauss Creamed Chipped Beef 4.4 -> 26.5) - the same
        # "single good attribute laundering a junk product" failure the
        # whole-grain weight fix caught on candy-coated cereal bars.
        facts = CATEGORY_FACTS.get(category, {})
        if (product.get("ingredients") or "").strip():
            meat_weight = facts.get("meat_sourcing_weight_with_ingredients", 0.10)
        else:
            meat_weight = facts.get("meat_sourcing_weight", 0.32)
        _use(meat, meat_weight); has_core_signal = True

    # organic_bonus and external_processing are context/tiebreaker signals,
    # not primary evidence - external_processing in particular defaults to a
    # neutral 70 when NOVA data is simply missing, precisely so a missing
    # OUTSIDE opinion doesn't swing a score that's otherwise built on real
    # ingredient/nutrition analysis. Found 2026-09-11 auditing top-3-per-
    # category: several "variety pack" bundle products (Goldfish variety
    # packs, granola bar multi-packs) carry NO ingredient list and NO
    # nutrition panel at all, so every core sub-score above is inapplicable -
    # with nothing gating them, organic_bonus (weight 0, inert) and
    # external_processing's neutral 70 became the ENTIRE score, letting a
    # complete data void quietly outrank real, honestly-analyzed competitors
    # in crackers and granola_bars. A product with no real signal at all must
    # not get a numeric score built purely from a "no opinion either way"
    # default - so these two are only included once at least one core
    # sub-score actually applies.
    if has_core_signal:
        _use(organic, organic_weight)
        if external.get("applicable"):
            _use(external, weights.get("external_processing", 0))

    score_cap = None
    if not has_core_signal:
        total = None
    else:
        total_weight = sum(w for _, w in components)
        total = round(sum(s * w for s, w in components) / total_weight, 1) if total_weight else None
        # Collect the ceilings that apply to this product, then clamp. Stored
        # on the record as `score_cap` so a diet profile re-weighting these
        # sub-scores in the browser clamps to the same ceiling - a low-sodium
        # profile must not be able to lift bacon above the processed-meat cap.
        # `caps` holds only the PRODUCT caps - the ones that follow from what
        # the thing is (cured meat, a bottle of seed oil, pure sugar). They are
        # stored as `score_cap` and are fixed.
        #
        # The severity-3 ingredient cap is deliberately NOT in there: it
        # follows from the user's own flagged-ingredient settings, which are
        # editable in the browser. Someone who turns off "hydrogenated oil"
        # should not still be silently capped by it. The browser re-derives it
        # from flagged.max_severity under their config; Python applies the
        # default here so the stored total matches the default settings.
        caps = []
        if ((meat.get("is_processed_meat") or _is_cured_meat_product(product))
                and not _is_seafood(product)):
            caps.append(CURED_MEAT_CAP)
        if _primary_seed_oil(product):
            caps.append(SEED_OIL_PRIMARY_CAP)
        if _primary_sweetener(product):
            caps.append(SWEETENER_PRIMARY_CAP)
        sugar_cap = _sugar_dose_cap(product)
        if sugar_cap is not None:
            caps.append(sugar_cap)
        score_cap = min(caps) if caps else None
        if total is not None and score_cap is not None:
            total = min(total, score_cap)
        if total is not None and flagged.get("max_severity", 0) >= 3:
            total = min(total, SEVERE_INGREDIENT_CAP)

    carcinogens = detect_carcinogens(product, meat)
    nut_flags = nutrition_flags(product)
    ing_banners = ingredient_banners(product)

    return {
        "sku": product.get("sku"),
        "name": product.get("name"),
        "brand": product.get("brand"),
        "price": product.get("price"),
        "image_url": product.get("image_url"),
        "aisle": product.get("aisle"),
        "total_score": total,
        "score_cap": score_cap,
        "sub_scores": {
            "ingredient_simplicity": simplicity,
            "flagged_ingredients": flagged,
            "nutrition": nutrition,
            "whole_food_processing": processing,
            "organic_bonus": organic,
            "external_processing": external,
            "whole_grain": whole_grain,
            "produce_freshness": freshness,
            "egg_husbandry": husbandry,
            "meat_sourcing": meat,
        },
        "carcinogens": carcinogens,
        "nutrition_flags": nut_flags,
        "ingredient_banners": ing_banners,
        "ingredients": product.get("ingredients"),
    }


def load_profile(name: str = "default") -> dict:
    with open(SCRIPTS_DIR / f"profile_{name}.json") as f:
        return json.load(f)
