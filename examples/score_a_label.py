"""
Score a few example labels with the real scoring engine - no store data needed.

    python3 examples/score_a_label.py

Each product is just what's printed on the package: the ingredient list and the nutrition panel
(per serving). The scorer turns that into a 0-100 score and explains every part of it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scoring"))
from scorer import compute_score, load_profile


def label(name, ingredients, category, **nutrition):
    """A product in the shape the scorer reads. Nutrition values are per serving."""
    units = {"calories": "calorie", "sodium": "milligram"}
    return name, category, {
        "name": name,
        "ingredients": ingredients,
        "nutrition": {k.replace("_", " "): {"size": v, "unit": units.get(k, "gram")} for k, v in nutrition.items()},
        "category_breadcrumb": "",
    }


EXAMPLES = [
    label("Natural peanut butter", "Peanuts, Salt", "peanut_butter",
          calories=190, sodium=110, saturated_Fat=3, added_Sugars=0, protein=7),
    label("Conventional peanut butter", "Roasted Peanuts, Sugar, Hydrogenated Vegetable Oils (Rapeseed, Cottonseed, Soybean), Salt",
          "peanut_butter", calories=190, sodium=140, saturated_Fat=3.5, added_Sugars=3, protein=7),
    label("Cola", "Carbonated Water, High Fructose Corn Syrup, Caramel Color, Phosphoric Acid, Natural Flavors, Caffeine",
          "cola", calories=140, sodium=45, added_Sugars=39, total_Sugars=39),
    label("Prebiotic soda", "Carbonated Water, Apple Cider Vinegar, Cane Sugar, Agave Inulin, Natural Flavors, Lime Juice, Stevia",
          "soda", calories=25, sodium=10, added_Sugars=4, total_Sugars=5),
]

profile = load_profile("default")
for name, category, product in EXAMPLES:
    r = compute_score(product, profile, category=category)
    cap = f"  (capped at {r['score_cap']})" if r.get("score_cap") else ""
    print(f"\n{name}: {r['total_score']}{cap}")
    for key, sub in r["sub_scores"].items():
        if sub.get("applicable") and sub.get("score") is not None:
            print(f"   {key.replace('_', ' '):<22} {sub['score']:>5}   {sub.get('explanation') or ''}")
