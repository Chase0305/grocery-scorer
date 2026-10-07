"""Parsing helpers for raw ingredient-list strings."""
import re

# ---------------------------------------------------------------------------
# Boilerplate "small amount" qualifiers that introduce a sub-list but aren't
# ingredients themselves.
#
# The original pattern here only matched "contains N% or less of". A survey of
# every colon-preceding phrase across 1,647 real ShopRite ingredient lists
# showed that phrasing is barely a quarter of the real usage:
#
#      69  "less than 2% of"                   <- was NOT matched
#      69  "contains 2% or less of"            <- matched
#      36  "contains less than 2% of"          <- was NOT matched
#      33  "contains 2% or less of each of the following"
#      17  "contains less than 2% of each of the following"
#      17  "contains one or more of the following"
#       3  "contains <2% of"   3  "less than 1% of"   2  "<1% of"   ...
#
# An unmatched qualifier doesn't vanish - it glues onto the ingredient that
# follows it, producing entries like "Contains Less Than 2% of: Salt". That
# mostly just looks bad, but it also defeats the _NEUTRAL_INGREDIENTS check in
# the scorer (which compares against the literal string "salt"), so salt in a
# trailing qualifier list gets penalized while salt elsewhere does not.
#
# SAFETY: every alternative below must end at a colon. That anchor is what
# keeps the percentage clause from eating real ingredients - "Reduced Fat 2%
# Milk" has no colon after the qualifier and cannot match, and even an
# explicit "2% Milk:" fails because the colon must follow the qualifier
# itself, not an intervening word.
_FILLER_RE = re.compile(
    r"""
    (?:\band\s+)?
    (?:\bmay\s+)?
    # "with" is consumed along with the qualifier so that
    # "Water with 2% or Less of Dextrose" resolves to Water + Dextrose.
    # Leaving it behind orphaned the connector into a fragment literally
    # named "Water with", inventing a non-existent ingredient.
    (?:\bwith\s+)?
    (?:\bcontains?\s+)?
    # A bare percentage is NEVER enough on its own. Every branch below demands
    # a qualifier marker - "less than", "or less", or a trailing "of".
    #
    # This is the second attempt. The first ended the pattern with a lookahead
    # for ":" or whitespace, which matched the "2%" inside "Reduced Fat 2%
    # Milk" and split it into "Reduced Fat" + "Milk" - inventing an ingredient
    # and corrupting a real one. The regression harness caught it; a spot
    # check would not have.
    (?:
        less\s+than\s+ <?\s* NUM \s* (?:%|percent) (?:\s*or\s+less)? (?:\s+of)?
      | <?\s* NUM \s* (?:%|percent) \s* or\s+less (?:\s+of)?
      | <?\s* NUM \s* (?:%|percent) \s+ of
      | one\s+or\s+more (?:\s+of)?
    )
    (?:\s+(?:each\s+of\s+)?the\s+following)?
    \s*:?
    """.replace("NUM", r"(?: \d+\s*/\s*\d+ | \d+(?:\.\d+)? )"),
    re.IGNORECASE | re.VERBOSE,
)

# Section HEADINGS, as opposed to component names. Both are spelled
# "Something:" but they mean opposite things, and conflating them was the
# worst bug in the first draft of this fix:
#
#   "Cottage Cheese: Cultured Skim Milk, Cream, Salt"   <- a component. The
#       milk/cream/salt are ingredients OF the cottage cheese, so nesting is
#       correct and the product really does have 1 top-level ingredient here.
#
#   "Inactive Ingredients: Carmine, Eucalyptus Oil, ..." <- a heading. What
#       follows is the product's ordinary ingredient list, NOT sub-parts of
#       a thing called "Inactive Ingredients". Nesting it collapsed an
#       8-ingredient cough drop to ONE and pushed it from 60 to 82 - a
#       heavily processed product suddenly scoring like whole food.
#
# Headings are therefore stripped (their contents stay top-level), exactly
# like the "less than 2%" qualifiers above.
#
# "Vitamins and Minerals:" is deliberately treated as a heading too. It is
# genuinely arguable either way - a parenthesised "Vitamin Blend (...)" would
# nest - but stripping keeps the ingredient count HIGHER and the score LOWER,
# and when a label is ambiguous this project's standing rule is to take the
# reading that cannot inflate a score.
def _is_section_label(header: str) -> bool:
    h = header.strip().lower()
    if re.search(r"\bingredients?$", h):          # other/inactive/active/"apples & cinnamon" ingredients
        return True
    if re.fullmatch(r"vitamins?\s*(?:and|&|/)\s*minerals?", h):
        return True
    if re.fullmatch(r"minerals?\s*(?:and|&|/)\s*vitamins?", h):
        return True
    if re.fullmatch(r"vitamins?|minerals?", h):
        return True
    # Dosing preambles on medicines/supplements: "In each 15 mL dose: ..."
    if re.match(r"^in\s+each\b", h):
        return True
    return h in ("cured with", "breaded with", "made with", "prepared with")

_MADE_FROM_RE = re.compile(r"^made\s+from\s+", re.IGNORECASE)

# Statements that are punctuated exactly like a component sub-list but are
# regulatory warnings, not ingredients. Only three products in the corpus, but
# nesting them would invent an ingredient called "Phenylketonurics".
_NON_INGREDIENT_HEADERS = ("phenylketonuric",)

# A component header: a short name followed by a colon, introducing that
# component's own ingredients - "Cottage Cheese: Cultured Skim Milk, Cream".
# Deliberately bounded in length and forbidden from containing commas or
# brackets, so it can only ever match a genuine label-style header.
_COLON_HEADER_MAX_LEN = 45

_OPENERS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {v: k for k, v in _OPENERS.items()}


def split_top_level(text: str) -> list[str]:
    """Split an ingredient string on commas, but only at bracket depth 0."""
    depth = 0
    parts = []
    current = []
    for ch in text:
        if ch in _OPENERS:
            depth += 1
            current.append(ch)
        elif ch in _CLOSERS:
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _depth0_colon(item: str) -> int:
    """Index of the first colon that is NOT inside brackets, or -1."""
    depth = 0
    for idx, ch in enumerate(item):
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return idx
    return -1


def _nest_colon_sublists(text: str) -> str:
    """Rewrite colon-delimited component sub-lists into bracket form.

        "Cottage Cheese: Cultured Skim Milk, Cream, Salt, Peach Prep: Peaches"
     -> "Cottage Cheese (Cultured Skim Milk, Cream, Salt), Peach Prep (Peaches)"

    Why this exists: manufacturers express the same nesting two ways, with
    parentheses or with a colon. The parser understood only parentheses, so a
    colon-style label had every sub-ingredient promoted to top level. Since
    ingredient_simplicity scores as 100 - (count-1)*12, that punished products
    purely for their label's punctuation - a multi-component item like a frozen
    meal ("Cheese Sticks: ..., Marinara Sauce: ...") counted 33 top-level
    ingredients instead of 2. Converting to bracket form lets one well-tested
    code path handle both styles and makes the two spellings score alike.

    A sub-list runs until the next component header or the end of the string.
    That is the ordinary reading of these labels, and it is also the
    conservative choice: the alternative (guessing where a component ends and
    top-level resumes) would silently drop real ingredients from the count.
    """
    items = split_top_level(text)
    out: list[str] = []
    group: tuple[str, list[str]] | None = None

    def flush():
        nonlocal group
        if group is None:
            return
        header, subs = group
        out.append(f"{header} ({', '.join(subs)})" if subs else header)
        group = None

    for item in items:
        idx = _depth0_colon(item)
        header = item[:idx].strip() if idx != -1 else ""

        # A header can trail the end of a previous sentence, which happens on
        # variety packs that list several flavours in one field:
        #   "...Natural Flavor.\nCINNAMON & SPICE INGREDIENTS: Sugar, ..."
        prefix = ""
        if header:
            m = re.search(r"[.\n]\s*([^.\n]*)$", header)
            if m:
                prefix, header = header[: m.start()].strip(" ."), m.group(1).strip()

        is_header = (
            idx != -1
            and 0 < len(header) <= _COLON_HEADER_MAX_LEN
            and re.search(r"[a-z]", header, re.IGNORECASE) is not None
            and not any(bad in header.lower() for bad in _NON_INGREDIENT_HEADERS)
        )

        # A section heading is dropped entirely and whatever follows stays at
        # the level we're already at - inside the current component if we're
        # in one, top-level otherwise.
        if is_header and _is_section_label(header):
            if prefix:
                (group[1] if group is not None else out).append(prefix)
            rest = item[idx + 1:].strip()
            if rest:
                (group[1] if group is not None else out).append(rest)
            continue

        if is_header:
            flush()
            if prefix:
                out.append(prefix)
            rest = item[idx + 1:].strip()
            group = (header, [rest] if rest else [])
        elif group is not None:
            group[1].append(item)
        else:
            out.append(item)

    flush()
    return ", ".join(out)


# Characters some labels use INSTEAD of commas to separate ingredients.
#
# Chosen by auditing every candidate against the real catalog (2026-09-15)
# rather than adding them one bug at a time, which is how the newline case
# was handled and why the semicolon case was missed:
#   semicolon  129 products, genuinely separators ("Purified Water;
#              Magnesium Sulfate; Potassium Chloride")          -> INCLUDED
#   newline     59, bullets 17                                  -> INCLUDED
#   slash    1,533 products, but it is "93 mg/l" and
#            "VITAMINS/MINERALS" - a unit and a compound term    -> EXCLUDED
#   " - "      377, but it is "Olive Oil - Composed of Refined
#              Olive Oil", a description not a list              -> EXCLUDED
#   asterisk   618, but it is a FOOTNOTE marker stuck to an
#              ingredient ("Magnesium Sulfate*")                 -> stripped, not split
# Splitting on the excluded three would have invented thousands of fake
# ingredients.
_SEPARATOR_RE = re.compile(r"[;\r\n\u2022\u00b7\u25cf\u25aa]+")
# Footnote markers and their legend, e.g. "Magnesium Sulfate* *for taste".
_FOOTNOTE_RE = re.compile(r"\*+")


def _prepare(raw: str) -> str:
    """Shared normalization: strip lead-ins, drop 'less than 2%' style
    qualifiers, then convert colon sub-lists to bracket form. Both public
    parsers run this so top-level and flattened views never disagree about
    the structure of the same label."""
    # Some labels separate ingredients with NEWLINES or bullets rather than
    # commas. Found 2026-09-15 when the user spot-checked "Dunkin' Extra Extra
    # Coffee Creamer, 48 fl oz" against shoprite.com: Open Food Facts stored
    # "SKIM MILK\nCANE SUGER\nWATER", which the comma-only splitter counted as
    # ONE ingredient - a perfect 100 for simplicity and a score of 95.6, while
    # its own 32 fl oz sibling (real comma-separated label, 8 ingredients)
    # scored 37.9. 86 products in the catalog split differently on newlines
    # than on commas. Normalising to commas first means both parsers and every
    # sub-score see the same structure.
    text = _SEPARATOR_RE.sub(", ", raw.strip())
    text = _FOOTNOTE_RE.sub("", text)
    text = _MADE_FROM_RE.sub("", text)
    text = _FILLER_RE.sub(",", text)
    return _nest_colon_sublists(text)


def top_level_ingredients(raw: str) -> list[str]:
    """Return the top-level ingredient names, filtering out boilerplate connector phrases."""
    if not raw:
        return []
    items = split_top_level(_prepare(raw))
    # Drop empty/near-empty fragments left behind by the filler substitution
    return [i for i in items if i and not _FILLER_RE.fullmatch(i)]


def flatten_all_mentions(raw: str) -> list[str]:
    """Every ingredient mention including nested sub-ingredients inside brackets, flattened."""
    if not raw:
        return []
    # Strip bracket characters but keep their contents as ordinary comma-separated text
    flat = re.sub(r"[()\[\]{}]", ",", _prepare(raw))
    items = [i.strip() for i in flat.split(",")]
    return [i for i in items if i]


def max_nesting_depth(raw: str) -> int:
    depth = 0
    max_depth = 0
    for ch in raw or "":
        if ch in _OPENERS:
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch in _CLOSERS:
            depth = max(0, depth - 1)
    return max_depth
