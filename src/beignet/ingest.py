"""Ingest ladder: get raw ingredient text from a YouTube video.

Rungs, tried in order:
  1. description    - ingredient list written in the video description
  2. linked_recipe  - description links to a recipe page

Each rung returns the ingredient section as text, headings and all; the LLM extract
step decides what is an ingredient.
"""
import html
import json
import re
from typing import TypedDict

import httpx
from yt_dlp import YoutubeDL

URL_RE = re.compile(r"https?://[^\s<>\"')]+")
FRACTIONS = "¼½¾⅓⅔⅛"
# Line starting with a quantity: "2 cloves garlic", "1/2 tsp", "1 1/2 tbsp", "1 ½ cups", "½ cup", "200g", "5 to 6 tbsp"
QTY_LINE_RE = re.compile(
    rf"^\s*[-*•▢]?\s*(\d+(\s+\d+/\d+|\s*[{FRACTIONS}]|[./]\d+)?|[{FRACTIONS}])"
    r"\s*((-|to)\s*\d+([./]\d+)?)?\s*[a-zA-Z]"
)
# "Soy sauce   25 grams", "Chicken 250~350 grams": name then amount+unit at line end
TRAILING_QTY_RE = re.compile(
    r"^\s*[-*•]?\s*[^\d\n]{2,40}?[\s\u3000]+\d+([./~-]\d+)?\s*"
    r"(g|kg|grams?|ml|l|liters?|oz|lbs?|cups?|tbsp|tsp|tablespoons?|teaspoons?|cloves?|pieces?)\s*$",
    re.IGNORECASE,
)
JSONLD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
# Links that are never recipe pages
SKIP_HOSTS = (
    "youtube.com", "youtu.be", "instagram.com", "facebook.com", "twitter.com",
    "x.com", "tiktok.com", "patreon.com", "amazon.", "amzn.to", "discord.", "bit.ly",
)
MIN_LIST_LINES = 3
# Description lines kept around the ingredient span, for headings ("Marinade:") and
# amount-less lines ("Salt to taste", "Lemon wedges, for garnish").
CONTEXT_LINES = 3
TAG_RE = re.compile(r"<[^>]+>")
HEADING_RE = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
BLOCK_TAG_RE = re.compile(r"</?(li|p|h[1-6]|div|br|tr|ul|ol)\b[^>]*>", re.IGNORECASE)
NON_TEXT_RE = re.compile(r"<(script|style|svg|button)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
SECTION_START_RE = re.compile(r"^(recipe\s+)?ingredients?\b", re.IGNORECASE)
SECTION_END_RE = re.compile(
    r"^(instructions?|directions?|method|steps|notes?|nutrition|equipment|storage)\b", re.IGNORECASE
)


class Ingested(TypedDict):
    title: str
    raw_text: str
    ingest_source: str | None  # "description" | "linked_recipe" | None
    source_url: str | None


def fetch_video_info(url: str) -> tuple[str, str]:
    """(title, description) of the video."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info.get("title") or "", info.get("description") or ""


def is_ingredient_line(line: str) -> bool:
    return bool(QTY_LINE_RE.match(line) or TRAILING_QTY_RE.match(line))


def description_ingredients(description: str) -> str | None:
    """Ingredient span of the description (plus surrounding context lines), or None if no list."""
    lines = [" ".join(l.split()) for l in description.splitlines()]
    hits = [i for i, l in enumerate(lines) if is_ingredient_line(l)]
    if len(hits) < MIN_LIST_LINES:
        return None
    start = max(0, hits[0] - CONTEXT_LINES)
    end = min(len(lines), hits[-1] + 1 + CONTEXT_LINES)
    return "\n".join(l for l in lines[start:end] if l)


def candidate_links(description: str) -> list[str]:
    seen, out = set(), []
    for url in URL_RE.findall(description):
        url = url.rstrip(".,;:!?")
        if url in seen or any(h in url.split("/")[2] for h in SKIP_HOSTS):
            continue
        seen.add(url)
        out.append(url)
    return out


def _iter_nodes(data):
    if isinstance(data, list):
        for d in data:
            yield from _iter_nodes(d)
    elif isinstance(data, dict):
        yield data
        yield from _iter_nodes(data.get("@graph", []))


def recipe_from_html(page: str) -> dict | None:
    """First schema.org Recipe node in page JSON-LD, else None."""
    for blob in JSONLD_RE.findall(page):
        try:
            data = json.loads(html.unescape(blob).strip())
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(data):
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if "Recipe" in kinds and node.get("recipeIngredient"):
                return node
    return None


def _html_lines(fragment: str) -> list[str]:
    text = html.unescape(TAG_RE.sub("", BLOCK_TAG_RE.sub("\n", NON_TEXT_RE.sub("", fragment))))
    return [" ".join(l.replace("▢", "").split()) for l in text.splitlines() if l.strip()]


def ingredients_from_html(page: str) -> list[str]:
    """Text of the page's ingredient section, keeping group headings ("Marinade:").

    A page can have several "Ingredients" headings (blog notes, recipe card); the one whose
    section has the most quantity lines wins.
    """
    headings = [(m.start(), m.end(), " ".join(html.unescape(TAG_RE.sub("", m.group(2))).split()))
                for m in HEADING_RE.finditer(page)]
    best: list[str] = []
    for i, (_, h_end, title) in enumerate(headings):
        if not SECTION_START_RE.match(title):
            continue
        end = next((s for s, _, t in headings[i + 1:]
                    if SECTION_END_RE.match(t) or SECTION_START_RE.match(t)), len(page))
        lines = _html_lines(page[h_end:end])
        if sum(map(is_ingredient_line, lines)) > sum(map(is_ingredient_line, best)):
            best = lines
    return best


def fetch_linked_recipe(links: list[str], client: httpx.Client) -> tuple[str, str] | None:
    for link in links:
        try:
            resp = client.get(link, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError:
            continue
        # Prefer the HTML section: unlike JSON-LD recipeIngredient it keeps group headings.
        lines = ingredients_from_html(resp.text)
        if sum(map(is_ingredient_line, lines)) < MIN_LIST_LINES:
            recipe = recipe_from_html(resp.text)
            lines = [html.unescape(i).strip() for i in recipe["recipeIngredient"]] if recipe else []
        if len(lines) >= MIN_LIST_LINES:
            return "\n".join(lines), str(resp.url)
    return None


def ingest_video(url: str, description: str | None = None, title: str = "") -> Ingested:
    if description is None:
        title, description = fetch_video_info(url)

    block = description_ingredients(description)
    if block:
        return {"title": title, "raw_text": block, "ingest_source": "description", "source_url": url}

    with httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0 (beignet)"}) as client:
        found = fetch_linked_recipe(candidate_links(description), client)
    if found:
        text, page_url = found
        return {"title": title, "raw_text": text, "ingest_source": "linked_recipe", "source_url": page_url}

    return {"title": title, "raw_text": "", "ingest_source": None, "source_url": None}
