/* Shared data loading + search logic for the landing-page prototypes
   (prototype_a_console.html, prototype_b_market.html, prototype_c_ledger.html).
   Each prototype explores a different visual/structural direction, but all
   three need the same real data: the full 17,787-product catalog crossed
   with the ~1,750 already-scored products, so "not yet scored" is honest
   rather than every full-catalog hit pretending to have a grade. */
window.GS = (function () {
  let CATALOG = {};
  let SKU_DETAIL = {};  // sku -> full scored record (total_score, sub_scores, aisle, category) - only for the ~1,750 hand-curated products
  let FULL_CATALOG = {};
  let SEARCH_INDEX = [];

  /* Load the slim files from scripts/build_app_data.py. They hold exactly what
     scoring and the cards read; the long explanation strings and raw ingredient
     lists arrive later via ensureDetail(). If any slim file is missing the old
     full files are used instead, so a forgotten build can never leave the app
     empty - it is only slower. */
  async function loadSlim() {
    const get = async u => {
      const r = await fetch(u, { cache: 'no-store' });
      if (!r.ok) throw new Error(u + ' ' + r.status);
      return r.json();
    };
    performance.mark('gs:start');
    const [curated, scored, catalog] = await Promise.all([
      get('/data/app/curated.json'), get('/data/app/scored.json'), get('/data/app/catalog.json')]);
    performance.mark('gs:downloaded+parsed');
    for (const [cat, items] of Object.entries(curated))
      if (Array.isArray(items) && items.length) {
        CATALOG[cat] = items;
        for (const item of items) if (item.sku) SKU_DETAIL[item.sku] = { ...item, category: cat };
      }
    let n = 0;
    for (const [sku, item] of Object.entries(scored))
      if (!(sku in SKU_DETAIL)) { SKU_DETAIL[sku] = item; n++; }
    FULL_CATALOG = catalog;
    performance.mark('gs:assembled');
    return n;
  }

  // Explanations (breakdown) and raw ingredient lists (buy-or-make) are only
  // read after a tap, so they are not part of the page load. Fetched once.
  let DETAIL_PROMISE = null, DETAIL_READY = false;
  function detailReady() { return DETAIL_READY; }
  function ensureDetail() {
    if (DETAIL_READY) return Promise.resolve();
    if (DETAIL_PROMISE) return DETAIL_PROMISE;
    DETAIL_PROMISE = (async () => {
      try {
        const d = await (await fetch('/data/app/detail.json', { cache: 'no-store' })).json();
        for (const [sku, row] of Object.entries(d)) {
          const subs = SKU_DETAIL[sku] && SKU_DETAIL[sku].sub_scores;
          if (row.e && subs)
            for (const [k, text] of Object.entries(row.e)) if (subs[k]) subs[k].explanation = text;
          if (row.i && FULL_CATALOG[sku]) FULL_CATALOG[sku].ingredients = row.i;
        }
        DETAIL_READY = true;
      } catch (e) { DETAIL_PROMISE = null; }     // offline or missing: try again next tap
    })();
    return DETAIL_PROMISE;
  }

  async function loadData() {
    let fullScoredCount = 0;
    let slimOk = false;
    try { fullScoredCount = await loadSlim(); slimOk = true; }
    catch (e) { CATALOG = {}; SKU_DETAIL = {}; FULL_CATALOG = {}; }
    if (!slimOk) {
    let cats = [];
    try {
      const html = await (await fetch('/data/', { cache: 'no-store' })).text();
      cats = [...new Set([...html.matchAll(/scores_([a-z0-9_]+)\.json/g)].map(m => m[1]))];
    } catch (e) {}

    await Promise.all(cats.map(async c => {
      try {
        const items = await (await fetch(`/data/scores_${c}.json`, { cache: 'no-store' })).json();
        if (Array.isArray(items) && items.length) CATALOG[c] = items;
      } catch (e) {}
    }));

    for (const [cat, items] of Object.entries(CATALOG))
      for (const item of items)
        if (item.sku) SKU_DETAIL[item.sku] = { ...item, category: cat };

    // Broader (but shallower) coverage: every full-catalog product that has
    // real ingredient data gets scored on the 4 category-agnostic sub-scores
    // (score_full_catalog.py), even outside the ~50 hand-curated categories.
    // Curated entries win on overlap - they carry category-specific bonuses
    // (organic weight, whole-grain, produce freshness, egg husbandry) this
    // broader pass can't apply without a real category_facts match.
    try {
      const fullScored = await (await fetch('/data/full_catalog_scored.json', { cache: 'no-store' })).json();
      for (const [sku, item] of Object.entries(fullScored)) {
        if (!(sku in SKU_DETAIL)) { SKU_DETAIL[sku] = item; fullScoredCount++; }
      }
    } catch (e) {}

    try {
      FULL_CATALOG = await (await fetch('/data/full_catalog_enriched.json', { cache: 'no-store' })).json();
    } catch (e) { FULL_CATALOG = {}; }
    DETAIL_READY = true;    // the full files already carry explanations and ingredients
    }

    try {
      PROFILES = await (await fetch('/data/profiles.json', { cache: 'no-store' })).json();
    } catch (e) { PROFILES = {}; }
    try {
      const defs = await (await fetch('/scripts/flagged_ingredients.json', { cache: 'no-store' })).json();
      for (const v of Object.values(defs))
        if (v && v.label && v.severity != null) FLAG_DEFS[v.label] = v.severity;
    } catch (e) { FLAG_DEFS = {}; }
    try {
      const saved = JSON.parse(localStorage.getItem(FLAG_KEY) || '{}');
      if (saved && typeof saved === 'object') FLAG_PREFS = saved;
    } catch (e) { FLAG_PREFS = {}; }
    try {
      const saved = localStorage.getItem('groceryscorer_profile_v1');
      if (saved && PROFILES[saved]) PROFILE = saved;
    } catch (e) {}

    const base = Object.keys(FULL_CATALOG).length ? FULL_CATALOG
      : Object.fromEntries(Object.values(CATALOG).flat().map(p => [p.sku, p]));
    performance.mark('gs:before-index');
    SEARCH_CACHE.clear(); BEST_CACHE.clear();
    SEARCH_INDEX = Object.values(base).map(p => ({
      ...p,
      _name: (p.name || '').toLowerCase(),
      _brand: (p.brand || '').toLowerCase(),
      // Precomputed by build_app_data.py; normalised here only if a record lacks it.
      _norm: p._n != null ? p._n : normalise((p.name || '') + ' ' + (p.brand || '')),
    }));

    performance.mark('gs:index-built');
    return {
      scoredCount: Object.values(CATALOG).reduce((a, v) => a + v.length, 0),
      broaderScoredCount: fullScoredCount,
      totalCount: SEARCH_INDEX.length,
      categoryCount: Object.keys(CATALOG).length,
    };
  }

  /* ---------------------------------------------------------------- filters
     Two deliberately DIFFERENT mechanisms, because the two use cases have
     opposite failure modes.

     Allergen / diet ("only show gluten free") keys off ShopRite's OWN
     diet_tags, present on 17,040 of 17,787 products. It is a SHOW-ONLY
     filter: a product qualifies only if the store affirmatively tags it.
     Inferring "no wheat in the ingredient list, therefore gluten free" would
     be unsafe - it misses cross-contamination, barley in "natural flavors",
     and shared lines - and someone filtering for coeliac reasons is exactly
     who must not be told a guess. Products with no tag are UNKNOWN and are
     hidden rather than shown, with the count surfaced so the user can see
     what they are not being shown.

     Ingredient preference ("no seed oils") keys off the flagged-ingredient
     labels scorer.py already computes, and is a HIDE filter: it removes
     confirmed matches and leaves unknowns visible. A preference wrongly
     showing you a product is a minor annoyance; an allergen filter wrongly
     showing you one is not. */
  function dietTags(sku) {
    const p = FULL_CATALOG[sku];
    const raw = p && p.diet_tags;
    if (!raw) return [];
    return (Array.isArray(raw) ? raw : [raw]).map(t => String(t).trim().toLowerCase());
  }

  function flaggedLabels(sku) {
    const d = SKU_DETAIL[sku];
    const f = d && d.sub_scores && d.sub_scores.flagged_ingredients;
    return (f && f.matched) || [];
  }

  // Returns {keep, reason} so the UI can explain what it filtered and why.
  function passesFilters(sku, filters) {
    const req = filters.requireTags || [];
    const avoid = filters.avoidFlags || [];
    if (req.length) {
      const tags = dietTags(sku);
      for (const r of req) {
        if (!tags.includes(r.toLowerCase()))
          return { keep: false, reason: tags.length ? 'not-tagged' : 'unknown' };
      }
    }
    if (avoid.length) {
      const flags = flaggedLabels(sku);
      for (const a of avoid) if (flags.includes(a)) return { keep: false, reason: 'avoided' };
    }
    return { keep: true };
  }

  function applyFilters(results, filters) {
    if (!(filters.requireTags || []).length && !(filters.avoidFlags || []).length)
      return { kept: results, hidden: 0, unknown: 0 };
    let hidden = 0, unknown = 0;
    const kept = results.filter(p => {
      const r = passesFilters(p.sku, filters);
      if (!r.keep) { hidden++; if (r.reason === 'unknown') unknown++; }
      return r.keep;
    });
    return { kept, hidden, unknown };
  }

  /* ---------------------------------------------------------------- price
     Price and a per-ounce figure, computed here rather than read from the
     scored file on purpose: scripts/price_signal.py is designed to be
     removable, and showing the price should not stop working if the user
     turns that feature off. Both values come straight from the catalog.

     ShopRite writes these for humans ("$3.99", "$0.20 avg/ea", "16.9 fl oz"),
     so anything unparseable simply returns null and the UI omits it rather
     than inventing a number. */
  const _SIZE_RE = /(\d+(?:\.\d+)?)\s*(fl oz|oz|lb|lbs|g|kg|ml|l)\b/i;
  const _PRICE_RE = /\$\s*(\d+(?:\.\d+)?)/;
  const _PER_OZ = { 'oz': 1, 'fl oz': 1, 'lb': 16, 'lbs': 16, 'g': 1 / 28.35,
                    'kg': 35.27, 'ml': 1 / 29.57, 'l': 33.8 };

  function priceFor(sku) {
    const p = FULL_CATALOG[sku] || SKU_DETAIL[sku];
    return (p && p.price) ? String(p.price) : null;
  }

  function unitPrice(sku) {
    const p = FULL_CATALOG[sku] || SKU_DETAIL[sku];
    if (!p) return null;
    const size = _SIZE_RE.exec(p.name || '');
    const price = _PRICE_RE.exec(String(p.price || ''));
    if (!size || !price) return null;
    const value = parseFloat(size[1]);
    if (!(value > 0)) return null;
    const per = _PER_OZ[size[2].toLowerCase()];
    if (!per) return null;
    const ounces = per * value;
    if (!ounces) return null;
    return { perOz: parseFloat(price[1]) / ounces, unit: /fl oz|ml|\bl\b/i.test(size[2]) ? 'fl oz' : 'oz' };
  }

  /* ------------------------------------------------------------- diet profiles
     A profile changes only the WEIGHTING. Every sub-score is a fact about the
     product, computed once by scorer.py; re-combining them here means the
     catalog is not re-scored (and the scoring logic not duplicated) once per
     profile.

     Two things a profile must NOT be able to do:
       - resurrect a missing sub-score. A profile that leans on nutrition still
         cannot judge a product with no nutrition panel; the sub-score stays
         inapplicable and the remaining weights renormalize, exactly as
         compute_score does.
       - beat a cap. `score_cap` on the record is the ceiling from processed
         meat / seed-oil bottles / pure sweeteners / severity-3 ingredients.
         No diet preference lifts bacon above 50. */
  let PROFILES = {};
  let PROFILE = 'default';

  // Set by the last search(): the word that had to be dropped to find
  // anything, or null. The UI reads it to explain itself.
  let lastRelaxedWord = null;
  function relaxedWord() { return lastRelaxedWord; }

  /* ------------------------------------------------------------ price mode
     "Cheaper" never changes a score. It only changes the ORDER among products
     that are already good: anything within `window` points of the best match
     (and not below a floor of 60, unless the best itself is lower) counts as
     good enough, and those are sorted by price per ounce, cheapest first.
     Everything outside the window keeps its score order underneath.
       off       - best score first (the original behaviour, the default)
       balanced  - within 10 points of the best
       cheaper   - within 20 points of the best
     If fewer than half of the good-enough products have a price per ounce
     (produce sold "each", for one) the list is left in score order: sorting
     on a price most of them lack would just shuffle them. */
  const PRICE_KEY = 'groceryscorer_pricemode_v1';
  const PRICE_WINDOWS = { off: 0, balanced: 10, cheaper: 20 };
  let PRICE_MODE = 'off';
  try { const m = localStorage.getItem(PRICE_KEY); if (m in PRICE_WINDOWS) PRICE_MODE = m; } catch (e) {}
  function priceMode() { return PRICE_MODE; }
  function setPriceMode(m) {
    PRICE_MODE = m in PRICE_WINDOWS ? m : 'off';
    try { localStorage.setItem(PRICE_KEY, PRICE_MODE); } catch (e) {}
  }
  // items: products already in score order (best first); scoreOf: sku -> score|null
  function priceRerank(items, scoreOf) {
    const win = PRICE_WINDOWS[PRICE_MODE];
    if (!win || items.length < 2) return items;
    const top = scoreOf(items[0].sku);
    if (top == null) return items;
    const cutoff = Math.max(top - win, Math.min(top, 60));
    const good = [], rest = [];
    for (const p of items) {
      const sc = scoreOf(p.sku);
      (sc != null && sc >= cutoff ? good : rest).push(p);
    }
    /* A product flagged "cheapest in class" (price_signal.py) is cheap for a
       suspicious reason - $0.25/oz "extra virgin" olive oil is below the cost
       of the olives. Cheaper mode must not reward that, so a flagged product
       counts as unpriced: it stays in score order, after the honestly priced. */
    const flagged = sku => ((SKU_DETAIL[sku] || {}).price_flags || []).some(f => f.id === 'cheap_for_claim');
    const priced = good.map(p => ({ p, u: flagged(p.sku) ? null : unitPrice(p.sku) })).filter(x => x.u);
    if (priced.length * 2 < good.length) return items;
    const byPrice = new Map(priced.map(x => [x.p.sku, x.u.perOz]));
    // Stable: equal prices (and products with no price) keep score order.
    const ordered = good.slice().sort((a, b) => {
      const pa = byPrice.get(a.sku), pb = byPrice.get(b.sku);
      if (pa != null && pb != null) return pa - pb;
      if (pa != null) return -1;
      if (pb != null) return 1;
      return 0;
    });
    return ordered.concat(rest);
  }

  function profiles() { return PROFILES; }
  function currentProfile() { return PROFILE; }
  function setProfile(name) { PROFILE = PROFILES[name] ? name : 'default'; }

  // Re-score the nutrition sub-score from its raw values under this profile's
  // emphasis. Mirrors score_nutrition() in scorer.py: a nutrient that is
  // ABSENT is excluded, never read as zero.
  function nutritionUnder(sub, emphasis) {
    if (!sub || !sub.applicable) return null;
    const parts = [];
    const add = (value, score, weight) => {
      if (value == null) return;               // absent - excluded, not zero
      parts.push([score, weight]);
    };
    const sugar = sub.added_sugar_g, sodium = sub.sodium_mg, fat = sub.saturated_fat_g;
    add(sugar,  sugar === 0 ? 100 : Math.max(0, 100 - sugar * 15), emphasis.added_sugar ?? 1);
    // 140mg is the FDA's own "low sodium" threshold - below it, no penalty.
    add(sodium, sodium <= 140 ? 100 : Math.max(0, 100 - (sodium - 140) / 3), emphasis.sodium ?? 1);
    add(fat,    Math.max(0, 100 - fat * 15), emphasis.saturated_fat ?? 1);
    if (!parts.length) return null;
    const tw = parts.reduce((a, [, w]) => a + w, 0);
    return Math.round(parts.reduce((a, [sc, w]) => a + sc * w, 0) / tw);
  }

  /* Total score for a product under the named profile. Returns null when the
     product has no score at all, so "unscored" stays unscored. */
  /* --------------------------------------------------- flagged ingredients
     The fifteen-odd flagged categories ship with a severity each. Those are
     my opinion, not a fact, so they are editable: turn one off, or make it
     milder or harsher. Stored per-user and applied on top of the scored data
     rather than by re-scoring the catalog.

     What makes this cheap: the flagged sub-score already records WHICH
     categories matched. Re-deriving its score under different severities is
     the same arithmetic scorer.py does - 100 - (sum of severities x 12) -
     just with the user's numbers. */
  let FLAG_DEFS = {};                       // label -> default severity
  let FLAG_PREFS = {};                      // label -> severity (0 = off)
  const FLAG_KEY = 'groceryscorer_flagprefs_v1';

  function flagDefs() { return FLAG_DEFS; }
  function flagPrefs() { return FLAG_PREFS; }
  function setFlagPref(label, severity) {
    if (severity === FLAG_DEFS[label]) delete FLAG_PREFS[label];   // back to default
    else FLAG_PREFS[label] = severity;
    try { localStorage.setItem(FLAG_KEY, JSON.stringify(FLAG_PREFS)); } catch (e) {}
  }
  function resetFlagPrefs() {
    FLAG_PREFS = {};
    try { localStorage.removeItem(FLAG_KEY); } catch (e) {}
  }
  function severityOf(label) {
    return FLAG_PREFS[label] != null ? FLAG_PREFS[label] : (FLAG_DEFS[label] ?? 0);
  }
  function flagsCustomised() { return Object.keys(FLAG_PREFS).length > 0; }

  // Re-derive the flagged sub-score under the user's severities. Returns null
  // when nothing is customised, so the stored score is used untouched.
  function flaggedUnder(sub) {
    if (!sub || !sub.applicable || !flagsCustomised()) return null;
    const matched = sub.matched || [];
    let penalty = 0, maxSeverity = 0;
    for (const label of matched) {
      const sev = severityOf(label);
      penalty += sev;
      if (sev > maxSeverity) maxSeverity = sev;
    }
    return { score: Math.max(0, 100 - penalty * 12), maxSeverity };
  }

  function scoreUnder(sku, name) {
    const d = SKU_DETAIL[sku];
    if (!d || d.total_score == null) return d ? (d.total_score ?? null) : null;
    const prof = PROFILES[name || PROFILE];
    if (!prof) return d.total_score;
    if ((name || PROFILE) === 'default' && !flagsCustomised()) return d.total_score;

    const subs = d.sub_scores || {};
    let sum = 0, tw = 0, severity = (subs.flagged_ingredients || {}).max_severity || 0;
    for (const [key, sub] of Object.entries(subs)) {
      // `weight` is set by scorer.py exactly when the sub-score was used in
      // the total - that, not `applicable`, is the marker. organic_bonus is
      // the case that proves it: it carries a weight and contributes, but
      // never sets `applicable`, so keying off that dropped it and inflated
      // Chobani plain yogurt from 94.1 to 100.
      if (!sub || sub.weight == null) continue;
      // Generic sub-scores take the profile's weight; category-specific ones
      // (organic, whole grain, meat sourcing, produce freshness, egg
      // husbandry) keep the weight scorer.py applied, because those encode
      // facts about the food, not a health philosophy.
      const weight = prof.weights[key] != null ? prof.weights[key] : sub.weight;
      let score = sub.score;
      if (key === 'nutrition') {
        const re = nutritionUnder(sub, prof.nutrition_emphasis || {});
        if (re != null) score = re;
      }
      if (key === 'flagged_ingredients') {
        const re = flaggedUnder(sub);
        if (re) { score = re.score; severity = re.maxSeverity; }
      }
      sum += score * weight; tw += weight;
    }
    if (!tw) return d.total_score;
    let total = Math.round((sum / tw) * 10) / 10;
    if (d.score_cap != null) total = Math.min(total, d.score_cap);
    // The severity-3 ceiling follows the user's own settings: turn off
    // "hydrogenated oil" and it stops capping. Product caps (cured meat,
    // seed-oil bottles, pure sugar) are facts about the thing and never move.
    if (severity >= 3) total = Math.min(total, 50);
    return total;
  }

  function scoreFor(sku) { return scoreUnder(sku); }
  function scoredDetail(sku) { return SKU_DETAIL[sku] || null; }

  function scoreColor(s) {
    const hue = Math.max(0, Math.min(120, (s / 100) * 120));
    return `hsl(${hue}, 58%, 40%)`;
  }
  function grade(s) {
    if (s >= 93) return 'A+'; if (s >= 87) return 'A';  if (s >= 82) return 'A-';
    if (s >= 77) return 'B+'; if (s >= 72) return 'B';  if (s >= 67) return 'B-';
    if (s >= 62) return 'C+'; if (s >= 55) return 'C';  if (s >= 48) return 'C-';
    if (s >= 38) return 'D';  return 'F';
  }
  const pretty = c => (c || '').replace(/_/g, ' ').replace(/\b\w/g, m => m.toUpperCase());

  /* The store returns either a bare number ("15") or a department name
     ("PRODUCE DEPARTMENT"). A naked "15" reads like a score rather than a
     location, so number it explicitly. Only ever present on the ~1,750
     hand-curated products - the full-catalog crawl deliberately doesn't
     collect aisle (see crawl_full_catalog.py's docstring). */
  function aisleLabel(a) {
    if (!a) return null;
    const s = String(a).trim();
    if (/^\d+$/.test(s)) return `Aisle ${s}`;
    return s.replace(/\bDEPARTMENT\b/i, '').trim()
            .replace(/\w\S*/g, t => t[0].toUpperCase() + t.slice(1).toLowerCase());
  }

  /* Normalise both the query and the indexed text the same way, so "&" and
     "and" are the same word. Measured 2026-09-29: "macaroni and cheese"
     returned 1 product while "macaroni & cheese" returned 46, because the
     store writes "&" and people type "and". Also drops punctuation, which
     otherwise makes "kellogg's" and "kelloggs" different searches. */
  function normalise(text) {
    return (text || '').toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[''`]/g, '')
      .replace(/[^a-z0-9%. ]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  /* Search matches the WORDS, so it can't tell what kind of product you mean: "soda" put
     baking soda first, "tea" matched steak, "milk" was mostly milk chocolate and "bread"
     breadcrumbs. ShopRite's own category says what a product IS. Products filed under
     what you typed rank above products that merely mention it. Tried in order: the whole
     phrase, then its last word (queries are modifier-first: "olive OIL"), each as typed
     and then as a plural ("Oils", "Nut Butters"). Returns null when nothing is filed that
     way, so a brand or a dish name searches exactly as before. */
  function categoryTier(matches, q) {
    const words = q.split(' ');
    const last = words[words.length - 1];
    // Each level of the breadcrumb, normalised: "Bread & Bakery / Bread / Wheat Bread".
    const segs = p => p._segs || (p._segs = String(p.category_breadcrumb || '').split('/')
      .filter(x => x && x.toLowerCase() !== 'grocery').map(x => ' ' + normalise(x)));
    const plural = w => w.endsWith('s') ? w : (/(x|ch|sh)$/.test(w) ? w + 'es' : w + 's');
    const tries = [q, last, words.slice(0, -1).concat(plural(last)).join(' '), plural(last)].filter(t => t && t.length >= 3);
    // A category NAMED for it ("Wheat Bread", "Soda", "Iced Tea") beats one that only
    // mentions it ("Bread Mixes", "Bread & Bakery", "Nut Butters & Spreads").
    // Every form of the word counts at a level (union, not first-found): "chicken breast"
    // must include raw "Chicken Breasts", not stop at deli "Chicken Breast".
    for (const test of [(seg, t) => seg.endsWith(' ' + t), (seg, t) => (seg + ' ').includes(' ' + t + ' ')]) {
      const hit = matches.filter(p => segs(p).some(seg => tries.some(t => test(seg, t))));
      if (hit.length) return new Set(hit.map(p => p.sku));
    }
    return null;
  }


  /* Matching is by substring, so "whole" also hits "WHOLEsome Pantry" - and "whole milk"
     picked a fat-free milk (found 2026-10-02). Products where every typed word appears as
     a WHOLE word (plurals allowed) are the ones that are really what you asked for. */
  function wholeWordTier(matches, words) {
    // Singular and plural match each other: "bananas" finds "Fresh Organic Banana".
    const esc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const res = words.map(w => new RegExp('(^| )(' + [...new Set([w, w.replace(/s$/, ''), w.replace(/es$/, '')])].map(esc).join('|') + ')(s|es)?( |$)'));
    const hit = matches.filter(p => res.every(re => re.test(p._norm)));
    return hit.length && hit.length < matches.length ? new Set(hit.map(p => p.sku)) : null;
  }

  function searchUncached(query) {
    const q = normalise(query);
    if (!q) return [];
    const words = q.split(/\s+/);
    // A plural also finds a product NAMED in the singular: "bananas" has to find "Fresh
    // Organic Banana" (it found only frozen sliced ones, 2026-10-03), "limes" found nothing.
    // Only when the singular is the last word of the name - the thing itself - because a
    // singular earlier in a name is usually describing something else: egg PASTA, tortilla
    // CHIPS, olive OIL, cashew cookie BARS.
    const sing = {};
    for (const w of words) if (w.length >= 4 && w.endsWith('s') && !w.endsWith('ss'))
      sing[w] = new RegExp('(^| )(' + [w.slice(0, -1), w.endsWith('es') ? w.slice(0, -2) : null].filter(Boolean).join('|') + ')( fruit)?$');
    const head = p => p._head != null ? p._head : (p._head = normalise(p._name.replace(/,.*$/, '')));
    const hasWord = (p, w) => p._norm.includes(w) || (sing[w] ? sing[w].test(head(p)) : false);
    let matches = SEARCH_INDEX.filter(p => words.every(w => hasWord(p, w)));

    /* Every word has to match, which is right when it works and useless when
       it does not: "canned soup" matched NOTHING, because no product name
       contains both words even though the store sells 115 soups. When the
       strict pass finds nothing, drop the least selective word and try again
       - and tell the caller, so the UI can say what it did rather than
       silently returning something else. */
    let relaxed = null;
    if (!matches.length && words.length > 1) {
      /* Drop words from the FRONT, not by frequency. English grocery queries
         are modifier-first and head-noun-last - "canned soup", "greek
         yogurt", "organic whole milk" - so the last word is the thing you
         actually want. The first attempt at this dropped whichever word
         matched the most products, which for "canned soup" threw away "soup"
         and returned Spam. */
      for (let i = 1; i < words.length; i++) {
        const kept = words.slice(i);
        const found = SEARCH_INDEX.filter(p => kept.every(w => hasWord(p, w)));
        if (found.length) {
          matches = found;
          relaxed = words.slice(0, i).join(' ');
          break;
        }
      }
    }
    lastRelaxedWord = relaxed;
    // Score each match ONCE. The comparator used to call scoreFor() itself,
    // which is O(n log n) scorings for a broad query; the order is identical
    // because the comparison below is unchanged and Array.sort is stable.
    const scoreOf = new Map();
    for (const p of matches) scoreOf.set(p.sku, scoreFor(p.sku));
    // Typing a brand ("poppi", "chobani") means that brand. Matching is substring, so
    // "poppi" also hits Orville Redenbacher's "popping corn" - which, scoring 100, used
    // to come first. Exact brand matches go first; score order holds within each group.
    const brandHit = p => normalise(p.brand) === q;
    const anyBrand = matches.some(brandHit);
    const kept = relaxed ? words.slice(relaxed.split(' ').length) : words;
    const tier = anyBrand ? null : categoryTier(matches, kept.join(' '));
    const whole = wholeWordTier(matches, kept);
    matches.sort((a, b) => {
      if (anyBrand) { const ba = brandHit(a), bb = brandHit(b); if (ba !== bb) return ba ? -1 : 1; }
      if (tier) { const ta = tier.has(a.sku), tb = tier.has(b.sku); if (ta !== tb) return ta ? -1 : 1; }
      if (whole) { const wa = whole.has(a.sku), wb = whole.has(b.sku); if (wa !== wb) return wa ? -1 : 1; }
      const sa = scoreOf.get(a.sku), sb = scoreOf.get(b.sku);
      if (sa != null && sb != null) return sb - sa;
      if (sa != null) return -1;
      if (sb != null) return 1;
      // Neither scored: rank by how prominently the query sits in the name -
      // found 2026-09-12 spot-checking against the real ShopRite site: a
      // broad query like "peanut butter" has 308 name matches (95 of them
      // genuine jarred spreads, the rest candy/cereal/bars that happen to
      // mention it), and without this, real spreads could get buried behind
      // derivative products purely by catalog insertion order.
      const ia = a._name.indexOf(q), ib = b._name.indexOf(q);
      if (ia !== ib) return (ia === -1 ? 1e9 : ia) - (ib === -1 ? 1e9 : ib);
      return a._name.length - b._name.length;
    });
    if (PRICE_MODE !== 'off' && matches.some(p => scoreOf.get(p.sku) != null))
      matches = priceRerank(matches, sku => scoreOf.get(sku));
    // Default cap raised 2026-09-12 (was 20) after the same spot-check found
    // real, wanted products getting cut off - a broad query can have far
    // more than 20-30 genuine matches. Kept far above what any UI should
    // ever render in one page; callers slice further for actual display.
    return matches;
  }

  /* The meal shelf, the buy-or-make shelf and the shopping list all run the
     same handful of searches ("olive oil", "fresh garlic", "chicken breast"),
     and each one scans the whole index and scores every hit. Measured
     2026-09-30: one search ~94 ms, and rendering the shelf took 1.7 s. The key
     includes everything the ORDER depends on - diet profile and severity
     edits - so switching either gives fresh results. A hit must also restore
     lastRelaxedWord, which the UI reads to explain a dropped search word. */
  const SEARCH_CACHE = new Map();
  function search(query, limit) {
    const nq = normalise(query);
    if (!nq) return [];
    const key = nq + '|' + PROFILE + '|' + PRICE_MODE + '|' + JSON.stringify(FLAG_PREFS);
    let hit = SEARCH_CACHE.get(key);
    if (!hit) {
      const matches = searchUncached(query);       // sets lastRelaxedWord
      hit = { matches, relaxed: lastRelaxedWord };
      if (SEARCH_CACHE.size > 200) SEARCH_CACHE.clear();
      SEARCH_CACHE.set(key, hit);
    }
    lastRelaxedWord = hit.relaxed;
    return hit.matches.slice(0, limit || 500);
  }

  function byCategory(cat) { return CATALOG[cat] || []; }
  function categories() { return Object.keys(CATALOG); }
  function product(sku) { return FULL_CATALOG[sku]; }

  /* ------------------------------------------------------------- shopping list
     An entry is an OBJECT, not a bare sku:
       { q: "peanut butter" | null, sku: "0004...", checked: false }
     `q` is the thing you actually wanted ("peanut butter"); `sku` is the
     product currently chosen for it. Keeping both is what makes the list
     useful in a store - you shop for milk, not for a barcode, and you can
     swap the pick without losing the item.

     v1 stored a flat array of skus. Those lists are migrated in place rather
     than dropped: an old entry becomes { q: null, sku, checked: false }. */
  const MY_LIST_KEY = 'groceryscorer_mylist_v1';

  function loadMyList() {
    try {
      const saved = JSON.parse(localStorage.getItem(MY_LIST_KEY) || '[]');
      if (!Array.isArray(saved)) return [];
      return saved.map(e => {
        if (typeof e === 'string') return { q: null, sku: e, checked: false };   // v1
        if (e && typeof e === 'object' && (e.sku || e.q))
          return { q: e.q || null, sku: e.sku || null, checked: !!e.checked, pinned: !!e.pinned,
                   ...(Number(e.uses) > 1 ? { uses: Number(e.uses) } : {}),   // planner: how many meals need it
                   ...(typeof e.note === 'string' && e.note ? { note: e.note.slice(0, 60) } : {}),   // the amount to buy
                   ...(cleanAmts(e.amts) ? { amts: cleanAmts(e.amts) } : {}) };                       // meal id -> that meal's amount
        return null;
      }).filter(e => e && (e.q || (e.sku && FULL_CATALOG[e.sku])));
    } catch (e) { return []; }
  }
  // Untrusted on load like everything in localStorage: short string keys and values only.
  function cleanAmts(a) {
    if (!a || typeof a !== 'object' || Array.isArray(a)) return null;
    const out = {};
    for (const [k, v] of Object.entries(a).slice(0, 40))
      if (typeof v === 'string' && v && k.length <= 40) out[k] = v.slice(0, 30);
    return Object.keys(out).length ? out : null;
  }
  function saveMyList(list) {
    try { localStorage.setItem(MY_LIST_KEY, JSON.stringify(list)); } catch (e) {}
  }

  /* Best product for a search term: highest score among real matches, with
     the user's own filters applied so a gluten-free shopper never gets a
     "best pick" they cannot eat. Returns the top few so the UI can offer
     alternatives without searching again. */
  const BEST_CACHE = new Map();
  function bestFor(query, filters, limit) {
    const key = normalise(query) + '|' + (limit || 6) + '|' + JSON.stringify(filters || null)
      + '|' + PROFILE + '|' + PRICE_MODE + '|' + JSON.stringify(FLAG_PREFS);
    const hit = BEST_CACHE.get(key);
    if (hit) { lastRelaxedWord = hit.relaxed; return hit.result.slice(); }
    const result = bestForUncached(query, filters, limit);
    if (BEST_CACHE.size > 400) BEST_CACHE.clear();
    BEST_CACHE.set(key, { result, relaxed: lastRelaxedWord });
    return result.slice();
  }
  function bestForUncached(query, filters, limit) {
    const raw = search(query);
    const { kept } = applyFilters(raw, filters || { requireTags: [], avoidFlags: [] });
    // Deliberately NOT category-tiered like search(): meal and recipe terms were each
    // checked against these picks, and tiering moved 21 of 133 - "lemon" to a lemon-lime
    // soda, "bell peppers" to a jar of roasted peppers (2026-10-02). Auto-picks stay
    // score-first; search and the list picker, where a person chooses, get the tiers.
    // Whole-word matches first ("whole milk" is not "Wholesome ... fat free milk"), then score.
    const nq = normalise(query).split(' ');
    const whole = wholeWordTier(kept, lastRelaxedWord ? nq.slice(lastRelaxedWord.split(' ').length) : nq);
    // Ties (many plain foods score exactly 100) go to products filed under what was asked
    // for, so "bananas" is fresh bananas (category: bananas) rather than a 48 oz bag of
    // sliced frozen ones (mixed fruit). Only a tie-break: a lemon-lime soda can't tie a lemon.
    const cat = categoryTier(kept, lastRelaxedWord ? nq.slice(lastRelaxedWord.split(' ').length).join(' ') : nq.join(' '));
    // Snack-pack and spray formats lose ties to the plain product: "olive oil" picked an olive-oil
    // cooking spray and "almonds" 100-calorie snack packs (both 100, like the bottle and the bag).
    const ODD = /\b(spray|100 calorie|calorie packs?|snack packs?|to go|on the go|single serve|pouch(es)?)\b/i;
    const askedOdd = ODD.test(query);
    const withScores = kept
      .map(p => ({ p, s: scoreFor(p.sku), w: whole && whole.has(p.sku) ? 1 : 0, c: cat && cat.has(p.sku) ? 1 : 0,
                   o: !askedOdd && ODD.test(p.name || '') ? 1 : 0 }))
      .filter(x => x.s != null)
      // Within a point counts as a tie: salted fire-roasted almonds (100) beat plain whole almonds
      // (99.3) on a rounding-level difference, not on anything that matters.
      .sort((a, b) => (b.w - a.w) || (Math.abs(b.s - a.s) >= 1 ? b.s - a.s : 0) || (a.o - b.o) || (b.c - a.c) || (b.s - a.s));
    if (PRICE_MODE !== 'off' && withScores.length > 1) {
      const sc = new Map(withScores.map(x => [x.p.sku, x.s]));
      const re = priceRerank(withScores.map(x => x.p), sku => sc.get(sku));
      withScores.length = 0;
      re.forEach(p => withScores.push({ p, s: sc.get(p.sku) }));
    }
    // Nothing scored? Fall back to unscored matches so the item is at least
    // on the list, rather than silently vanishing.
    const pool = withScores.length ? withScores.map(x => x.p) : kept;
    return pool.slice(0, limit || 6);
  }

  /* Where to look for it in the store. ShopRite's aisle data is inconsistent
     (documented in the README), so this degrades on purpose: a real aisle if
     there is one, else the department from the breadcrumb, else "Other". */
  function aisleGroup(sku) {
    const p = FULL_CATALOG[sku];
    if (!p) return 'Other';
    const a = aisleLabel(p.aisle);
    if (a) return a;
    const parts = String(p.category_breadcrumb || '').split('/').filter(Boolean);
    const dept = parts[0] === 'Grocery' ? parts[1] : parts[0];
    return dept || 'Other';
  }

  return { loadData, ensureDetail, detailReady, search, scoreFor, scoredDetail, priceFor, unitPrice, dietTags, flaggedLabels, passesFilters, applyFilters, scoreColor, grade, pretty, aisleLabel, byCategory, categories, product, loadMyList, saveMyList, bestFor, aisleGroup, profiles, relaxedWord, currentProfile, setProfile, scoreUnder, priceMode, setPriceMode, flagDefs, flagPrefs, setFlagPref, resetFlagPrefs, severityOf, flagsCustomised };
})();
