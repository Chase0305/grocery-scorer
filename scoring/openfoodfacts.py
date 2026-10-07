"""
Open Food Facts lookup by UPC. Free, public, no API key needed - but we
still rate-limit and cache aggressively, same policy as the ShopRite
scraper, out of basic courtesy to a free community-run service.

Gives us NOVA group (1-4, standardized food-processing classification)
and Nutri-Score as an external, non-hand-tuned quality signal to sit
alongside our own ingredient analysis.
"""
import json
import time
from pathlib import Path

import requests

USER_AGENT = "GroceryHealthScorer/1.0 (personal project, not for redistribution)"
FIELDS = "product_name,nova_group,nutriscore_grade,nutriscore_score,ingredients_analysis_tags,additives_tags,status"

# Everything FIELDS has, plus the raw ingredient text and the nutrient table.
# Kept separate rather than folded into FIELDS because the two uses are
# genuinely different: FIELDS backs score_external_processing(), which only
# ever wants NOVA/Nutri-Score as an outside opinion. EXTENDED_FIELDS is for
# asking the much bigger question of whether OFF could *replace* ShopRite as
# the source of ingredients and nutrition. Widening FIELDS would silently
# make every existing lookup heavier for no benefit.
EXTENDED_FIELDS = (
    FIELDS
    + ",ingredients_text,ingredients_text_en,brands,serving_size,serving_quantity,nutriments"
)

MIN_REQUEST_INTERVAL_SECONDS = 1.5

# Responses are cached on disk by (upc, fieldset). Open Food Facts is a free,
# donation-funded community service; re-asking it for data we already have is
# both slow for us and rude to them. Also makes comparison runs repeatable
# and free after the first pass.
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "off"

_last_request_time = 0.0


def _wait_for_rate_limit():
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    remaining = MIN_REQUEST_INTERVAL_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)


class LookupFailed(Exception):
    """Network/transport error - distinct from a confirmed 'not in database'
    result, so callers know not to cache this as a permanent answer."""


def _cache_path(upc: str, fields: str) -> Path:
    # Fieldset is part of the key: a cached FIELDS response doesn't contain
    # ingredients, so serving it to an EXTENDED_FIELDS caller would look like
    # "OFF has no ingredients for this product" when we simply never asked.
    tag = "ext" if fields == EXTENDED_FIELDS else "base"
    return CACHE_DIR / f"{upc}.{tag}.json"


def fetch_by_upc(upc: str, fields: str = FIELDS, use_cache: bool = True) -> dict | None:
    """Return the Open Food Facts product dict, or None if genuinely not found.
    Raises LookupFailed on network errors so those aren't mistaken for
    (and cached as) a real "not found" result.

    A confirmed "not in the database" IS cached (as null) - that's a real
    answer, and re-asking every run would waste a request per miss forever.
    """
    cache_file = _cache_path(upc, fields)
    if use_cache and cache_file.exists():
        cached = json.loads(cache_file.read_text())
        return cached.get("product")

    _wait_for_rate_limit()
    url = f"https://world.openfoodfacts.org/api/v2/product/{upc}.json"
    try:
        resp = requests.get(url, params={"fields": fields}, headers={"User-Agent": USER_AGENT}, timeout=15)
        # Open Food Facts returns HTTP 404 *with* a valid JSON body (status:0)
        # for a genuine "not in our database" answer - that's a real,
        # cacheable result, not a transport failure. Only treat responses
        # we can't even parse, or server errors, as failures worth retrying.
        if resp.status_code >= 500:
            resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise LookupFailed(str(e)) from e
    finally:
        global _last_request_time
        _last_request_time = time.monotonic()

    product = data.get("product") if data.get("status") == 1 else None
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"upc": upc, "product": product}, indent=2))
    return product
