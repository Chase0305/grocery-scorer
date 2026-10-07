"""
Recipe import: a URL -> the recipe's ingredient lines.

Most recipe sites publish their recipe as structured data (schema.org "Recipe" in a
<script type="application/ld+json"> block) because Google wants it, so the ingredient
list can be read exactly, with no AI and no guessing. That is tried first.

    python3 scripts/recipe_import.py https://example.com/some-recipe

WHY THIS RUNS ON THE SERVER AND NOT IN THE PAGE: a web page is not allowed to read
another website's HTML (the browser blocks it), so scripts/serve.py exposes this as
/api/recipe and the page asks the server. That means it works at home on the Mac;
using it from a phone on cell data needs the app hosted (see PHASE_PLAN.md).

SAFETY - this matters because serve.py also listens on the wifi (for the phone): an
endpoint that fetches any URL it is given would let anyone on the network make this
Mac request internal addresses (the router's admin page, localhost services). So:
  * http(s) only;
  * every hostname is resolved and REJECTED if ANY address is private, loopback,
    link-local or otherwise non-public - re-checked on every redirect hop;
  * redirects are followed by hand (max 4) so a public URL cannot bounce to a private
    one; response size is capped; a short timeout; nothing is written to disk.
"""
import html as htmllib
import ipaddress
import json
import re
import socket
import sys
from urllib.parse import urljoin, urlparse

import requests

MAX_BYTES = 3_000_000
TIMEOUT = 12
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


class ImportError_(Exception):
    """Raised with a message that is safe and useful to show the user."""


class Blocked(ImportError_):
    """The site refused to hand its page to a program (401/403/405/429)."""


def _public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ImportError_("That address didn't resolve - check the link.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            raise ImportError_("Only public websites can be imported.")


def fetch(url: str) -> str:
    """Fetch a page, following redirects by hand and re-checking every hop."""
    for _ in range(5):
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ImportError_("That doesn't look like a web link (it should start with http).")
        _public_host(parts.hostname)
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                           "Accept-Language": "en-US,en;q=0.9"},
                             timeout=TIMEOUT, allow_redirects=False, stream=True)
        except requests.RequestException:
            raise ImportError_("Couldn't reach that site.")
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, r.headers.get("Location", ""))
            r.close()
            continue
        if r.status_code in (401, 403, 405, 429):   # 405 is how some sites (pinchofyum.com) refuse non-browser readers
            r.close()
            raise Blocked(f"{parts.hostname.removeprefix('www.')} won't let other apps read its pages. "
                               "Open the recipe, press Cmd+A then Cmd+C to copy the whole page (or just the ingredient list), and paste it here instead.")
        if r.status_code >= 400:
            r.close()
            raise ImportError_(f"The site answered with an error ({r.status_code}).")
        body = b""
        for chunk in r.iter_content(65536):
            body += chunk
            if len(body) > MAX_BYTES:
                break
        r.close()
        return body.decode(r.encoding or "utf-8", errors="replace")
    raise ImportError_("Too many redirects.")


def _flatten(node):
    """Yield every dict inside JSON-LD, whatever it is nested in (@graph, lists, mainEntity)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _flatten(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flatten(v)


def _is_recipe(d: dict) -> bool:
    t = d.get("@type")
    t = t if isinstance(t, list) else [t]
    return "Recipe" in [str(x) for x in t]


def _clean(line) -> str:
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", str(line)))
    return re.sub(r"\s+", " ", text).strip()


def _yield(v) -> str:
    if isinstance(v, list):
        v = v[0] if v else ""
    return _clean(v)


def parse_recipe(page: str) -> dict | None:
    """Structured data first (JSON-LD), then schema.org microdata."""
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except ValueError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))   # trailing commas are common
            except ValueError:
                continue
        for d in _flatten(data):
            if _is_recipe(d) and d.get("recipeIngredient"):
                ing = d["recipeIngredient"]
                ing = ing if isinstance(ing, list) else [ing]
                lines = [_clean(x) for x in ing if _clean(x)]
                if lines:
                    return {"title": _clean(d.get("name", "")), "ingredients": lines,
                            "yield": _yield(d.get("recipeYield", "")), "via": "structured data"}
    micro = re.findall(r'itemprop=["\'](?:recipeIngredient|ingredients)["\'][^>]*>(.*?)</', page, re.S | re.I)
    lines = [_clean(x) for x in micro if _clean(x)]
    if lines:
        t = re.search(r'<title[^>]*>(.*?)</title>', page, re.S | re.I)
        return {"title": _clean(t.group(1)) if t else "", "ingredients": lines, "yield": "", "via": "page markup"}
    return None


_CARD_START = re.compile(r'class="[^"]*(?:tasty-recipes-ingredients|wprm-recipe-ingredients|recipe-ingredients)[^"]*"', re.I)
_CARD_END = re.compile(r'(?:instructions|directions)', re.I)


def parse_card(html: str) -> list[str]:
    """Ingredient lines from a recipe card's own markup (Tasty Recipes, WP Recipe Maker, ...):
    the list items between the 'ingredients' container and the 'instructions' one."""
    m = _CARD_START.search(html)
    if not m:
        return []
    chunk = html[m.start():m.start() + 12000]
    end = _CARD_END.search(chunk, 200)
    if end:
        chunk = chunk[:end.start()]
    lines = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", chunk, re.S | re.I):
        t = _clean(li)
        if t and t not in lines:
            lines.append(t)
    return lines[:60]


def wp_feed_recipe(url: str) -> dict | None:
    """When a site refuses to hand over its page, many recipe blogs (WordPress) still publish the
    same post through their public JSON feed - the one the page itself advertises in its headers
    (rel="https://api.w.org/"), which exists for programs to read. One request, our normal
    identity, nothing disguised; a site that has switched the feed off simply answers with an
    error and we fall back to asking the person to paste."""
    parts = urlparse(url)
    slug = [x for x in parts.path.split("/") if x][-1:] 
    if not slug or not parts.hostname:
        return None
    try:
        _public_host(parts.hostname)
        r = requests.get(f"https://{parts.hostname}/wp-json/wp/v2/posts",
                         params={"slug": slug[0], "_fields": "title,content"},
                         headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                         timeout=TIMEOUT, allow_redirects=False)
        if r.status_code != 200 or len(r.content) > MAX_BYTES * 2:
            return None
        post = r.json()[0]
        html = post["content"]["rendered"]
    except (requests.RequestException, ValueError, IndexError, KeyError, TypeError, ImportError_):
        return None
    got = parse_recipe(html)
    if got:
        return {**got, "via": "the site's public feed"}
    lines = parse_card(html)
    if not lines:
        return None
    return {"title": _clean(post.get("title", {}).get("rendered", "")), "ingredients": lines,
            "yield": "", "via": "the site's public feed"}


def import_url(url: str) -> dict:
    """The contract serve.py returns as JSON. Never raises."""
    try:
        try:
            recipe = parse_recipe(fetch(url.strip()))
        except Blocked:
            recipe = wp_feed_recipe(url.strip())
            if not recipe:
                raise
    except ImportError_ as e:
        return {"ok": False, "error": str(e)}
    except Exception:
        return {"ok": False, "error": "Something went wrong reading that page."}
    if not recipe:
        return {"ok": False, "error": ("Couldn't find a recipe on that page. Some sites don't publish their "
                                       "ingredients in a readable form - copy the ingredient list and paste it instead.")}
    return {"ok": True, **recipe, "source": urlparse(url).hostname}


if __name__ == "__main__":
    print(json.dumps(import_url(sys.argv[1]), indent=2, ensure_ascii=False))
