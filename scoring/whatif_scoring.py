"""What-if scoring: re-score the whole catalog under the fixes proposed in SCORING_NOTES.md
(audit 2026-10-02), IN MEMORY ONLY. Nothing is written to data/ or to scorer.py.

    python3 scripts/whatif_scoring.py        # ~2.5 minutes

Prints three columns: today's score, variant A (sweetener + false-positive + fortification/water
fixes) and variant B (A, plus simplicity graded by what an ingredient is rather than how many).
"""
import json, sys, copy, re, collections, statistics as st
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scorer
from score_full_catalog import leaf_slug
from departments import is_non_food
from scorer import compute_score, load_profile, _in_meat_department
R=str(Path(__file__).resolve().parent.parent/'data')+'/'
CAT=json.load(open(R+'full_catalog_enriched.json')); STORED=json.load(open(R+'full_catalog_scored.json'))
prof=load_profile('default')
def run():
    out={}
    for sku,p in CAT.items():
        if sku not in STORED: continue
        category=leaf_slug(p.get('category_breadcrumb')) or ''
        off={"nova_group":p["nova_group"],"nova_inferred":p.get("nova_inferred")} if p.get("nova_group") is not None else None
        r=compute_score(p,prof,category=category,off_product=off)
        out[sku]=(r['total_score'],r)
    return out
base=run()
drift=sum(1 for k,(t,_) in base.items() if t is not None and abs(t-(STORED[k]['total_score'] or 0))>0.15)
print('baseline reproduces stored scores; products drifting >0.15:',drift,'of',len(base))

# ---- PROPOSALS ----
FC=scorer.FLAGGED_CATEGORIES
FC['added_sugar']['terms']+= ['cassava root syrup','cassava syrup','tapioca syrup','brown rice syrup','rice syrup','agave syrup','agave nectar','maple syrup','date syrup','cane juice','invert syrup','malt syrup','barley malt syrup','glucose syrup','apple juice concentrate','grape juice concentrate','pear juice concentrate']
FC['artificial_sweetener']={'label':'artificial sweetener','severity':2,'terms':['aspartame','sucralose','acesulfame','saccharin','neotame','advantame']}
scorer._NEUTRAL_INGREDIENTS |= {'water','filtered water','carbonated water','sparkling water','purified water','spring water','spices','natural spices',
  'niacin','reduced iron','iron','ferrous sulfate','thiamine mononitrate','thiamin mononitrate','thiamine','riboflavin','folic acid','vitamin d3','vitamin a palmitate'}
_orig_flag=scorer.score_flagged_ingredients
def patched_flag(product, category=''):
    t=product.get('ingredients') or ''
    t2=re.sub(r'(?i)sugar snap|honeydew','PEA',t)
    # "(preservative)" after an antioxidant vitamin is not a preservative additive
    t2=re.sub(r'(?i)(citric acid|ascorbic acid|tocopherols?|vitamin e|rosemary extract)\s*[\(\[][^\)\]]*preservative[^\)\]]*[\)\]]',r'\1',t2)
    return _orig_flag({**product,'ingredients':t2},category)
scorer.score_flagged_ingredients=patched_flag
new=run()

# A+: snap peas must not trip the 'first ingredient is sugar' cap
_ops=scorer._primary_sweetener
scorer._primary_sweetener=lambda p: _ops({**p,'ingredients':re.sub(r'(?i)sugar snap','snap',p.get('ingredients') or '')})
newA=run()
# B: kitchen-recognisable ingredients cost 5 points instead of 12
KITCHEN=re.compile(r"\b(water|juice|vinegar|salt|spices?|herbs?|garlic|onions?|peppers?|paprika|cumin|oregano|basil|parsley|thyme|rosemary|cinnamon|ginger|turmeric|nutmeg|tomato(es)?|lemon|lime|apples?|oranges?|berries|strawberr(y|ies)|blueberr(y|ies)|raspberr(y|ies)|cherr(y|ies)|grapes?|banana|mango|pineapple|peach(es)?|pears?|carrots?|celery|beets?|spinach|kale|potato(es)?|beans?|lentils|chickpeas|peas|corn|rice|oats?|wheat|flour|semolina|barley|quinoa|milk|cream|butter|eggs?|cheese|yogurt|cultures?|enzymes|yeast|olive oil|avocado oil|coconut( milk| oil)?|almonds?|peanuts?|cashews?|walnuts?|pecans?|seeds?|cocoa|chocolate|vanilla( extract)?|honey|maple syrup|sugar|chicken|beef|pork|turkey|fish|salmon|tuna|shrimp|mushrooms?|cucumbers?|squash|pumpkin|zucchini|broccoli|cabbage|lettuce|avocados?|dates|raisins|cassava root fiber|chicory root|inulin|tea|coffee)\b",re.I)
_FORT={'niacin','reduced iron','iron','ferrous sulfate','thiamine mononitrate','thiamin mononitrate','thiamine','riboflavin','folic acid','vitamin d3','vitamin a palmitate'}
from ingredients import top_level_ingredients, flatten_all_mentions
_orig_simp=scorer.score_ingredient_simplicity
def simpB(product, category=''):
    r=_orig_simp(product,category)
    if not r.get('applicable') or r.get('top_level_count',0)==0 or 'whole food' in (r.get('explanation') or ''): return r
    raw=product.get('ingredients') or ''
    top=[t.strip().lower() for t in top_level_ingredients(raw)]
    pen=0; first=True
    for t in top:
        core=re.sub(r'\b(organic|natural|fresh|filtered|carbonated|sparkling|pure|whole|dried|ground|\d+%)\b','',t).strip(' *.')
        if t in scorer._NEUTRAL_INGREDIENTS or core in _FORT: continue
        cost=5 if KITCHEN.search(core) and not re.search(r'(modified|hydrolyzed|isolate|concentrate|syrup|fructose|dextrose|maltodextrin|starch|gum|lecithin|acid|colou?r|caramel|flavou?r|extract(?<!vanilla extract)|powder)',core) else 12
        if first: first=False; continue        # the first real ingredient is free, as today
        pen+=cost
    nested=max(0,len(flatten_all_mentions(raw))-len(top))
    r={**r,'score':max(0,min(100,100-pen-nested*2))}
    return r
scorer.score_ingredient_simplicity=simpB
newB=run()
def s(k,src): v=src.get(k); return None if not v or v[0] is None else v[0]
names={k:STORED[k]['name'] for k in STORED}
def show(pattern, n=1):
    for k in [k for k in STORED if re.search(pattern,names[k],re.I)][:n]:
        print(f"   {s(k,base):>6}  A {s(k,newA):>6}  B {s(k,newB):>6}   {names[k][:58]}")
print('                 now      A          B')
for pat,n in [(r'^Poppi Prebiotic Soda (Cream|Grape)',2),(r'^Olipop Cream Soda, 12 fl oz$',1),(r'^Coca-Cola Original Taste Soda, 12 fl oz, 8',1),(r'^Coca-Cola Zero Sugar Cola, 12 fl oz, 12',1),(r'^Sprite Zero Sugar Lemon-Lime Soda, 12 fl oz, 12',1),(r'^Pepsi Cola, 2 liter',1),
  (r'Zero Calorie Sweetener with Sucralose',1),(r'^Gold Peak Zero Sugar Sweet Tea',1),(r'^Pero Family Farms Sugar Snap Peas, 8',1),(r'^Birds Eye Steamfresh Sugar Snap Peas',1),
  (r'^San Giorgio Elbow',1),(r'^Rao.s Homemade Marinara',1),(r'^Muir Glen Organic Tomato Basil Pasta Sauce',1),(r'^Pace Chunky Salsa',1),(r'^Amy.s Organic Lentil Soup',1),(r'^Planet Oat Original Oatmilk, 52',1),
  (r"^Kellogg's Froot Loops",1),(r'^Oreo Chocolate Sandwich Cookies',1),(r"^Doritos Nacho",1),(r'^Totino',1)]:
    show(pat,n)
for lab,src in [('A',newA),('B',newB)]:
    d=[(s(k,src)-s(k,base),k) for k in base if s(k,base) is not None and s(k,src) is not None]
    ch=[x for x in d if abs(x[0])>=0.5]
    print(f'\n{lab}: {len(ch)} products move 0.5+ (up {sum(1 for x in ch if x[0]>0)}, down {sum(1 for x in ch if x[0]<0)})')
    top_up=sorted(d,reverse=True)[:5]; top_dn=sorted(d)[:5]
    print('  biggest up:',[(round(x[0],1),names[x[1]][:35]) for x in top_up])
    print('  biggest down:',[(round(x[0],1),names[x[1]][:35]) for x in top_dn])
# does B keep junk below whole food? rank checks
def med(cat,src): v=[s(k,src) for k in STORED if STORED[k]['category']==cat and s(k,src) is not None]; return round(st.median(v),1) if v else None
print('\ncategory medians  now / A / B')
for c in ['red_sauces','salsa_dips','cola','lemon_lime_soda','cereal','cookies','chips','frozen_single_serve_meals','broth_stock','spaghetti_angel_hair','canned_beans','yogurt']:
    print(f'  {c:28} {med(c,base)} / {med(c,newA)} / {med(c,newB)}')

