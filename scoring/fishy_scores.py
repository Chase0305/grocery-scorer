"""
Weekly "fishy scores" check: find scores that look wrong, without changing any.

Each check is a pattern that has produced a real bad score before:
  thin_data_high     a 5+ ingredient product scoring 85+ with no nutrition panel (Talenti gelato sat at 100)
  sugary_high        10 g+ added sugar a serving (or a sugary drink) still scoring 60+
  sweet_soda_high    a sugar-sweetened soda above 25 (Coke is 15; Poppi is 45-56 on purpose)
  calorie_mismatch   calories don't match fat/carbs/protein - a garbled panel (the bad Coke 12-pack)
  size_spread        sizes of the same product scoring 15+ points apart
  category_outlier   a 4+ ingredient product at 90+ in a category whose middle score is under 40
  cut_off_list       an ingredient list that stops mid-way (unclosed bracket, trailing 'and' / '2% or less of')
  big_moves          scores that moved 20+ points since the catalog of N days ago (git history)

Writes audit/reports/<date>.md (readable) and audit/reports/<date>.json (everything).
Read-only over data/; run from the repo root:  python3 scripts/fishy_scores.py [--days 7]
"""
import argparse
import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORED = ROOT / "data" / "full_catalog_scored.json"
ENRICHED = ROOT / "data" / "full_catalog_enriched.json"
OUT = ROOT / "audit" / "reports"

SUGARS = r"\b(sugar|cane sugar|high fructose corn syrup|corn syrup|glucose-fructose|fructose|dextrose|honey|agave|syrup)\b"
FRESH = re.compile(r"/(produce|meat|seafood|fresh fruit|fresh vegetables)\b", re.I)
SIZE = re.compile(r",?\s*\d[\d.,/ ]*\s*(fl\.? ?oz|oz|lb|lbs|ct|count|pack|pk|g|kg|ml|l|liter|gallon|gal|qt|pint|pt)\b.*$", re.I)


def nut(r, key):
    v = (r.get("nutrition") or {}).get(key)
    try:
        return float(v["size"]) if isinstance(v, dict) and v.get("size") is not None else None
    except (TypeError, ValueError):
        return None


def old_scores(days):
    """{sku: total_score} from the last commit at least `days` old, or {} if git history is unavailable."""
    try:
        rev = subprocess.run(["git", "rev-list", "-1", f"--before={days} days ago", "HEAD", "--", str(SCORED.relative_to(ROOT))],
                             cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
        if not rev:
            return {}, None
        blob = subprocess.run(["git", "show", f"{rev}:data/full_catalog_scored.json"], cwd=ROOT,
                              capture_output=True, timeout=300).stdout
        return {k: v.get("total_score") for k, v in json.loads(blob).items()}, rev[:7]
    except (subprocess.SubprocessError, ValueError, OSError):
        return {}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    scored = json.loads(SCORED.read_text())
    enriched = json.loads(ENRICHED.read_text())
    hits = defaultdict(list)

    def add(check, sku, why):
        s = scored[sku]
        hits[check].append({"sku": sku, "name": s.get("name", "")[:80], "score": s.get("total_score"),
                            "category": s.get("category"), "why": why})

    by_cat = defaultdict(list)
    for sku, s in scored.items():
        by_cat[s.get("category")].append(s.get("total_score") or 0)
    cat_median = {c: statistics.median(v) for c, v in by_cat.items() if len(v) >= 10}

    groups = defaultdict(list)
    for sku, s in scored.items():
        e = enriched.get(sku, {})
        score = s.get("total_score")
        if score is None:
            continue
        bc = e.get("category_breadcrumb") or ""
        ing = (e.get("ingredients") or "").lower()
        cat = s.get("category") or ""
        has_panel = bool(e.get("nutrition"))

        n_ing = len([x for x in re.split(r",(?![^()]*\))", ing) if x.strip()])
        if score >= 85 and not has_panel and not FRESH.search("/" + bc) and n_ing >= 5:
            add("thin_data_high", sku, "no nutrition panel; scored on ingredients alone")

        added, total = nut(e, "added Sugars"), nut(e, "total Sugars")
        drink = "Beverages" in bc
        if score >= 60 and ((added is not None and added >= 10) or (drink and total is not None and total >= 15 and re.search(SUGARS, ing[:80]))):
            add("sugary_high", sku, f"added sugar {added} g, total {total} g per serving")

        if "Soda" in bc and score > 25 and re.search(SUGARS, ",".join(ing.split(",")[:2])) and (total or 0) >= 15:
            add("sweet_soda_high", sku, f"sugar in first two ingredients, {total} g sugar")

        cal, fat, carb, prot = (nut(e, k) for k in ("calories", "total Fat", "total Carbohydrate", "protein"))
        if None not in (cal, fat, carb, prot):
            est = 9 * fat + 4 * carb + 4 * prot
            if abs(est - cal) > 40 and abs(est - cal) > 0.4 * max(cal, est):
                add("calorie_mismatch", sku, f"label says {cal:.0f} kcal, fat/carbs/protein add up to {est:.0f}")

        if cat in cat_median and cat_median[cat] < 40 and score >= 90 and n_ing >= 4:
            add("category_outlier", sku, f"category middle score is {cat_median[cat]:.0f}")

        tail = ing.rstrip(" .")
        if score >= 50 and ing and (ing.count("(") > ing.count(")") or re.search(r"(,|\band|\bof|less of|contains)$", tail)):
            add("cut_off_list", sku, f"list ends: ...{tail[-50:]}")

        base = SIZE.sub("", (s.get("name") or "")).strip().lower()
        if base:
            groups[(s.get("brand") or "").lower(), base].append(sku)

    for (brand, base), skus in groups.items():
        if len(skus) < 2:
            continue
        vals = sorted((scored[k]["total_score"], k) for k in skus)
        if vals[-1][0] - vals[0][0] >= 15:
            add("size_spread", vals[0][1], f"{len(skus)} sizes score {vals[0][0]}-{vals[-1][0]} (high: {vals[-1][1]})")

    old, rev = old_scores(args.days)
    for sku, s in scored.items():
        a, b = old.get(sku), s.get("total_score")
        if a is not None and b is not None and abs(a - b) >= 20:
            add("big_moves", sku, f"{a} -> {b} since {rev}")

    for v in hits.values():
        v.sort(key=lambda h: -(h["score"] or 0))

    today = dt.date.today().isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{today}.json").write_text(json.dumps({"date": today, "compared_to": rev, "hits": hits}, indent=1))

    lines = [f"# Fishy scores - {today}", "",
             f"{len(scored):,} scored products checked. Compared with commit {rev or '(no history available)'} for big moves.", "",
             "| Check | Count |", "|---|---|"]
    lines += [f"| {c} | {len(v)} |" for c, v in sorted(hits.items())]
    for c, v in sorted(hits.items()):
        lines += ["", f"## {c} ({len(v)})", ""]
        lines += [f"- **{h['score']}** {h['name']} (`{h['sku']}`, {h['category']}): {h['why']}" for h in v[:20]]
        if len(v) > 20:
            lines.append(f"- ... {len(v) - 20} more in {today}.json")
    (OUT / f"{today}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4 + len(hits) + 2]))
    print(f"\nwrote audit/reports/{today}.md")


if __name__ == "__main__":
    sys.exit(main())
