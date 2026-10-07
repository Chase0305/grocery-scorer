# Acesulfame potassium (Ace-K, E 950; Sunett, Sweet One)

*Researched 2026-10-03 by the scheduled research agent. Web searches returned abstracts and summaries; some pages (e.g. food-safety.com) were blocked by the network and I could not open full texts, so figures come from search summaries and are flagged where relevant.*

## Verdict

Acesulfame-K has been judged safe by regulators at normal intakes, and EFSA's 2025 re-evaluation actually *raised* its safe daily limit from 9 to 15 mg/kg/day. The human evidence of harm is one French cohort (NutriNet-Santé) showing a modest association with cancer and heart disease; the rest of the worrying data is from mice at high doses. It is almost never eaten alone: 97% of catalog products containing it also contain sucralose or aspartame, so it is effectively a marker of "diet / zero-sugar product". Severity 2 under the shared artificial-sweetener category is defensible; **keep as is**.

## Evidence grade

**Contested** on long-term disease risk; direct evidence of harm at real intakes is **Weak** (one cohort family, animal data at supraphysiological doses). The regulatory finding that normal intakes are within the ADI is **Strong** (JECFA, EFSA 2025, FDA).

## What the evidence says

**Regulators**
- JECFA and the former EU SCF set an ADI of 15 mg/kg bw/day (EU later used 9). EFSA's 2025 re-evaluation of E 950 set the ADI at 15 mg/kg bw/day, based on the highest no-effect dose in a chronic toxicity/carcinogenicity rat study, and concluded exposure estimates were generally below it in all population groups ([EFSA Journal 2025](https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2025.9317); summary via [food-safety.com](https://www.food-safety.com/articles/10526-efsa-reevaluates-safety-of-artificial-sweetener-acesulfame-k-raises-acceptable-daily-intake), snippet only). FDA lists it as an approved sweetener ([FDA](https://www.fda.gov/food/food-additives-petitions/aspartame-and-other-sweeteners-food)). Unlike aspartame, IARC has not classified it as possibly carcinogenic.
- Older rodent cancer signals (Soffritti, Ramazzini) were not accepted by regulators because of design problems ([PMC1570058](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1570058/)). *Animal, Weak.*

**Human cohort data**
- NutriNet-Santé, cancer (102,865 adults, median 7.8 y): acesulfame-K HR 1.13 (95% CI 1.01-1.26) for overall cancer, alongside aspartame HR 1.15. Authors acknowledge residual confounding and reverse causation; the cohort is self-selected and health-conscious ([sweeteners.org summary of the PLoS Med paper](https://www.sweeteners.org/scientific_studies/artificial-sweeteners-and-cancer-risk-results-from-the-nutrinet-sante-population-based-cohort-study/)). The much larger Nurses' Health Studies later found no breast-cancer association for aspartame (see [aspartame.md](aspartame.md)); I did not find an equivalent large null cohort specific to Ace-K.
- NutriNet-Santé, cardiovascular (103,388 adults): total artificial sweeteners, mainly aspartame and acesulfame-K, were associated with higher cerebrovascular disease; acesulfame-K and sucralose with higher coronary heart disease ([PMC9593923](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9593923/)). Same cohort, same limitations; because people who use diet products differ from those who don't (weight, diabetes, diet quality), this is hypothesis-generating. *Weak-to-Moderate association, causation unproven.*

**Mechanistic / animal (clearly not human intake data)**
- CD-1 mice, 4 weeks: altered gut microbiome and extra weight gain in males ([PLoS One 2017](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0178426)). C57BL/6 mice, 11 weeks: gut microbiota shifts, hepatic inflammation and triglyceride accumulation ([ScienceDirect 2024](https://www.sciencedirect.com/science/article/abs/pii/S2212429224015311)). Doses were large relative to human intake. A 2022 Wistar rat study found no effect on gut microbiome or metabolome ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0278691522003210)). *Weak and inconsistent.*
- Human trials: a 2022 review of sweeteners and gut microbiota found human results mostly null or inconsistent for Ace-K, with small, short studies ([Adv Nutr](https://advances.nutrition.org/article/S2161-8313(22)00198-3/fulltext)). A 2025 review concluded human studies generally confirm safety within the ADI while preclinical models show effects, often at supraphysiological levels ([PubMed 41337931](https://pubmed.ncbi.nlm.nih.gov/41337931/)).
- WHO's 2023 conditional recommendation against non-sugar sweeteners for weight control applies to the whole class (see [sucralose.md](sucralose.md)).

## Dose in real products

ADI for a 70 kg adult: 15 mg/kg x 70 = 1,050 mg/day. A 12 oz Coke Zero Sugar has about 46 mg ([search summary of Coca-Cola data](https://www.coca-cola.com/us/en/brands/coca-cola/products/zero)), so about 23 cans/day would reach the ADI; one can is about 4% of it. EFSA's exposure estimates: mean up to 5.2 mg/kg/day in toddlers and a 95th percentile of about 15.7 mg/kg/day for brand-loyal toddlers, i.e. only the extreme consumers approach the limit (EFSA summary, snippet). Children drinking multiple diet drinks a day are the group with the least margin.

## How the scorer treats it today

- `flagged_ingredients.json` -> `artificial_sweetener`, severity 2 (match term "acesulfame"; also covers "acesulfame potassium" and "acesulfame k"). 24 points off the flagged sub-score, once per product however many sweeteners it contains.
- No dedicated cap. It sits in the same bucket as sucralose, aspartame, saccharin, neotame and advantame.
- Because it nearly always co-occurs with another sweetener, a separate Ace-K rule would change almost nothing.

## Recommendation

**Keep as is** (severity 2). Evidence is no stronger or weaker than for sucralose/aspartame: contested, small association signals in observational data, regulators comfortable. If the owner wants to differentiate sweeteners, the better lever is the open question in the queue about saccharin/neotame/advantame (less regulatory evidence), not Ace-K. One side note: "acesulfame" as a match term is fine (no false positives expected).

## Products affected

**603** catalog products list acesulfame (about 3.6% of the 16,674 scored). Of these, 394 also list sucralose, 233 aspartame, and only about 19 contain Ace-K without either. Mean total_score 23.2, range 2.6-74.6. Examples:
- Bowl & Basket No Sugar Added Yellow Cling Diced Peaches in Water: 74.6 (the whole-fruit base keeps it high despite the flag)
- Pure Leaf Zero Sugar Real Brewed Sweet Tea, 6 ct: 65.1
- Gold Peak Zero Sugar Sweet Real Brewed Tea: 59.9
- Crystal Light Pink Lemonade Drink Mix: 2.6
- Pure Kick Energy Hydrate Low Calorie Drink Mix Variety Pack: 2.6

## Sources

- https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2025.9317
- https://www.food-safety.com/articles/10526-efsa-reevaluates-safety-of-artificial-sweetener-acesulfame-k-raises-acceptable-daily-intake
- https://www.fda.gov/food/food-additives-petitions/aspartame-and-other-sweeteners-food
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1570058/
- https://www.sweeteners.org/scientific_studies/artificial-sweeteners-and-cancer-risk-results-from-the-nutrinet-sante-population-based-cohort-study/
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9593923/
- https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0178426
- https://www.sciencedirect.com/science/article/abs/pii/S2212429224015311
- https://www.sciencedirect.com/science/article/abs/pii/S0278691522003210
- https://advances.nutrition.org/article/S2161-8313(22)00198-3/fulltext
- https://pubmed.ncbi.nlm.nih.gov/41337931/
- https://www.coca-cola.com/us/en/brands/coca-cola/products/zero
