# Aspartame (E 951; NutraSweet, Equal)

*Researched 2026-10-03 by the scheduled research agent. Web searches returned abstracts and summaries; I could not open every full text, so figures come from those summaries and are flagged where they do.*

## Verdict

At real-world intakes, aspartame has not been shown to cause cancer or other disease in people. IARC's "possibly carcinogenic" label (2B, July 2023) rests on limited human evidence for liver cancer, and the WHO/FAO expert committee (JECFA) looked at the same data on the same day and left the safe daily limit unchanged at 40 mg/kg. A 70 kg adult would need roughly 15-20 cans of diet soda every day to reach that limit. Severity 2 under "artificial sweetener" is a fair "not a health food" marker, and no change is needed. Recommendation: **keep as is**.

## Evidence grade

**Contested** on long-term disease risk. The direct evidence of harm at normal intakes is **Weak**: three liver-cancer cohorts and one French cohort, all observational and open to confounding and reverse causation. The regulatory finding that normal intakes are within the safe limit is **Strong** (EFSA 2013, JECFA 2023). Short RCTs showing no effect on glucose, gut microbiome or weight are **Moderate**.

## What the evidence says

**IARC vs JECFA, 14 July 2023 (same data, different questions)**
- IARC (hazard identification): Group 2B, "possibly carcinogenic to humans", on *limited* evidence for hepatocellular carcinoma in humans, plus limited evidence in animals and for mechanisms. Only three human studies of artificially sweetened beverages could speak to aspartame and liver cancer. All three found a positive association, but IARC said chance, bias or confounding could not be ruled out ([IARC summary](https://www.iarc.who.int/wp-content/uploads/2023/07/Summary_of_findings_Aspartame.pdf); [WHO news release](https://www.who.int/news/item/14-07-2023-aspartame-hazard-and-risk-assessment-results-released)).
- JECFA (risk assessment): found "no sufficient reason" to change the ADI of 0-40 mg/kg bw/day. It judged the evidence for cancer in humans "not convincing", because the studies measured exposure poorly and could not rule out other causes ([FAO/WHO](https://www.fao.org/food-safety/news/news-details/en/c/1644792/); [FSAI](https://www.fsai.ie/news-and-alerts/latest-news/aspartame-jefca-and-iarc-assessments)).
- How to read "2B": IARC grades how sure it is that something *can* cause cancer under some conditions, not how likely it is at a given dose. Group 2B also holds aloe vera extract and pickled vegetables. It says nothing about the amount needed.

**EFSA 2013 full re-evaluation:** aspartame and its breakdown products are safe for the general population, including infants, children and pregnant women. EFSA found no genotoxic or carcinogenic potential and kept the ADI at 40 mg/kg bw/day ([EFSA Journal](https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2013.3496)). Note that the FDA's ADI is higher, at 50 mg/kg.

**Cohorts on cancer**
- **NutriNet-Santé, Debras et al., PLoS Med 2022 (102,865 French adults, median 7.8 years):** higher aspartame intake was associated with overall cancer, HR 1.15 (95% CI 1.03-1.28), and breast cancer, HR 1.22 (1.01-1.48). The authors acknowledge selection bias, residual confounding and reverse causality ([PLoS Med](https://journals.plos.org/plosmedicine/article?id=10.1371%2Fjournal.pmed.1003950)). A modest association, but a single cohort of health-conscious volunteers.
- **Nurses' Health Studies, JNCI 2025 (10,814 invasive breast cancer cases, ~30 years, intake reassessed repeatedly):** HR 1.00 (0.98-1.03) per 200 mg/day, about one 12 oz diet soda, and the same after excluding the first 10 years of follow-up ([JNCI](https://academic.oup.com/jnci/article/117/4/795/7825366)). This is a larger, longer cohort with better exposure data, and it is null on exactly the cancer NutriNet-Santé flagged.

**Metabolic (human trials)**
- A 12-week double-blind RCT in healthy lean adults found no effect of aspartame on glycaemia, appetite or body weight ([Appl Physiol Nutr Metab](https://cdnsciencepub.com/doi/10.1139/apnm-2019-0359?mobileUi=0)). The crossover secondary analysis found no change in gut microbiota composition or faecal short-chain fatty acids with aspartame ([PMC7694690](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7694690/)). A meta-analysis of aspartame/ace-K blends on appetite and incretins found generally no effect ([PMC9776645](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9776645/)). These trials were small and short.
- General sweetener evidence (WHO 2023 conditional advice against using sweeteners for weight control; McGlynn 2022 JAMA Netw Open RCT meta-analysis showing small benefits when replacing sugary drinks) is covered in [sucralose.md](sucralose.md) and applies equally here.

**Phenylketonuria (PKU):** aspartame is half phenylalanine, so people with PKU must avoid it, which is why the label says "PHENYLKETONURICS: CONTAINS PHENYLALANINE". EFSA found normal intakes up to the ADI did not push plasma phenylalanine above clinical guidelines for people who are carriers. The ADI does not apply to PKU patients ([EFSA](https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2013.3496)). This is a real but tiny population-specific issue, not a general health signal.

**Animal studies:** the Ramazzini Institute rat studies (the oldest cancer signal) were reviewed by EFSA and JECFA and judged insufficient because of design problems. *Animal studies, treat as Weak.*

## Dose in real products

JECFA's own exposure estimates: mean 5 mg/kg/day for adults (10 for children), high consumers 12 mg/kg/day adults (20 children) ([JECFA summary via FAO](https://www.fao.org/fao-who-codexalimentarius/news-and-events/news-details/it/c/1644807/)). Even high consumers sit at about 30-50% of the ADI.

| Item | Aspartame | Share of EFSA/JECFA ADI (40 mg/kg), 70 kg adult = 2,800 mg |
|---|---|---|
| Diet Pepsi, 12 oz | ~120-130 mg (label) | ~4-5% |
| Diet Coke, 12 oz | ~125-300 mg (sources vary) | ~4-11% |
| Sugar-free gum, per piece | a few mg to ~20 mg | <1% |

Roughly 9-22 cans reach the ADI, depending on the brand. The NutriNet-Santé "high consumers" and the 200 mg/day Nurses' Health unit both correspond to about one diet soda a day, which is the practical range of interest. These per-can figures come from news and brand-specific web pages, not from a regulator table, so treat them as approximate.

## How the scorer treats it today

- `flagged_ingredients.json` → `artificial_sweetener`, **severity 2** (aspartame, sucralose, acesulfame, saccharin, neotame, advantame), added in the 2026-10-02 audit. Cost: 24 points of the flagged sub-score, counted once per product even if it has several sweeteners.
- No dedicated cap. Aspartame is never the first ingredient of any product, and `SWEETENER_PRIMARY_CAP` (40) applies only to added sugars as the primary sweetener.
- The category is shared, so aspartame is penalised the same as sucralose, saccharin and neotame. The evidence base differs a little (aspartame has the most regulatory scrutiny, saccharin and neotame much less), but not enough to justify a separate category.

## Recommendation

**Keep as is.** Severity 2 matches the "contested, low confidence of harm, not a health food" picture and keeps diet drinks below plain water-like scores without equating them to sugar or hydrogenated oil. Optional, low priority, if the owner wants a PKU note: add an informational banner "contains phenylalanine" in the app. The scorer already has `ingredient_banners`, and this is the label-mandated warning rather than a score effect.

## Products affected

**297** catalog products list aspartame (about 1.8% of the 16,674 scored products). By comparison, 603 products list acesulfame and 751 list sucralose in the enriched catalog. The main categories are gum and mints (48), cola (46), lemon-lime soda (32), iced tea (28) and powdered drink mixes (26). Scores range from 2.6 to 59.9 (mean about 25.9), but many of the lowest-scoring products are also penalised for other flags (for example Cool Whip Zero Sugar, 30.9, matches eight flagged categories including hydrogenated oil). Examples:
- Gold Peak Zero Sugar Sweet Tea, 59 fl oz: 59.9
- Snapple Zero Sugar Lemon Tea, 16 fl oz: 59.6
- Crystal Light Pink Lemonade Drink Mix: 2.6
- Mentos Pure Fresh Spearmint Sugarfree Gum: 2.6
- Cool Whip Zero Sugar Whipped Topping: 30.9

## Sources

- https://www.iarc.who.int/wp-content/uploads/2023/07/Summary_of_findings_Aspartame.pdf
- https://www.who.int/news/item/14-07-2023-aspartame-hazard-and-risk-assessment-results-released
- https://www.fao.org/food-safety/news/news-details/en/c/1644792/
- https://www.fao.org/fao-who-codexalimentarius/news-and-events/news-details/it/c/1644807/
- https://www.fsai.ie/news-and-alerts/latest-news/aspartame-jefca-and-iarc-assessments
- https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2013.3496
- https://journals.plos.org/plosmedicine/article?id=10.1371%2Fjournal.pmed.1003950
- https://academic.oup.com/jnci/article/117/4/795/7825366
- https://cdnsciencepub.com/doi/10.1139/apnm-2019-0359
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7694690/
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9776645/
