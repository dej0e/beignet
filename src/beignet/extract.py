"""LLM extraction: raw ingredient text -> structured ExtractionResult.

Provider and model config live in beignet.llm.
"""
import re
import sys
import time
from typing import get_args

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from beignet.llm import (BAD_REQUEST_ERRORS, RATE_LIMIT_ERRORS, TRANSIENT_ERRORS, provider_config,
                         structured_llm)
from beignet.schema import ExtractionResult, Ingredient, Unit

MAX_ATTEMPTS = 5
MAX_BACKOFF_S = 60.0
RETRY_TEMPERATURE = 0.3  # attempt 1 is deterministic; retries vary so a bad generation isn't repeated
# Unit fixes the model applies inconsistently, enforced after parsing.
COUNT_WORD_RE = re.compile(r"^\s*(pods?|pieces?|pcs?|numbers?|nos?\.?)\s*$", re.IGNORECASE)
BUNCH_WORD_RE = re.compile(r"\b(bundles?|bunch(es)?)\b", re.IGNORECASE)
UNITS = set(get_args(Unit))
# Unit spellings the model writes -> Unit enum. Keys are lowercased with trailing "s"/"." removed.
UNIT_ALIASES = {
    "tablespoon": "tbsp", "tb": "tbsp", "tbs": "tbsp", "tbl": "tbsp", "teaspoon": "tsp",
    "gram": "g", "gr": "g", "kilogram": "kg", "kilo": "kg", "milliliter": "ml", "millilitre": "ml",
    "liter": "l", "litre": "l", "ounce": "oz", "pound": "lb", "fl oz": "fl_oz", "fluid ounce": "fl_oz",
    "tin": "can", "bundle": "bunch",
    "piece": "each", "pc": "each", "pod": "each", "number": "each", "no": "each", "whole": "each",
}
RETRY_AFTER_RE = re.compile(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", re.IGNORECASE)

SYSTEM_PROMPT = """\
Extract the recipe's ingredients for grocery shopping. Fill the schema fields as their descriptions say; \
use your judgment for anything they leave open. Return the data itself, not the schema.
"""


class TruncatedOutput(Exception):
    """Model hit the output token limit; the JSON may still parse but be missing ingredients."""


def _invoke(temperature: float, messages: list) -> ExtractionResult:
    out = structured_llm(temperature).invoke(messages)
    if out["raw"].response_metadata.get("finish_reason") == "length":
        raise TruncatedOutput(f"output hit max_tokens={provider_config().max_output_tokens}")
    if out["parsing_error"]:
        raise out["parsing_error"]
    parsed = out["parsed"]
    if parsed is None:
        raise OutputParserException("model returned no structured output")
    if isinstance(parsed, ExtractionResult):
        return parsed
    return ExtractionResult.model_validate(coerce_units(parsed))


def coerce_units(data: dict) -> dict:
    """Map free-text units (the LLM schema allows any string) onto the Unit enum, in place.

    Unknown units become unit=None with the word kept in qualitative, per the schema's rule.
    """
    for ing in ((data.get("recipe") or {}).get("ingredients") or []):
        q = ing.get("quantity") or {}
        unit = q.get("unit")
        if not isinstance(unit, str):
            continue
        key = unit.strip().lower()
        if key not in UNITS:
            key = key.rstrip(".")
            key = UNIT_ALIASES.get(key) or UNIT_ALIASES.get(key.rstrip("s")) or (
                key.rstrip("s") if key.rstrip("s") in UNITS else None)
        if key is None:
            q["unit"] = None
            q["qualitative"] = q.get("qualitative") or unit.strip() or None
        else:
            q["unit"] = key
    return data


def _retry_delay(err: Exception, attempt: int) -> float | None:
    """Seconds to wait before retrying `err`, or None if it is not retryable."""
    if isinstance(err, RATE_LIMIT_ERRORS):
        header = err.response.headers.get("retry-after") if err.response is not None else None
        if header and header.replace(".", "", 1).isdigit():
            secs = float(header)
            return secs + 1 if secs + 1 <= MAX_BACKOFF_S else None
        m = RETRY_AFTER_RE.search(str(err))
        if m:
            minutes, amount, unit = m.groups()
            secs = float(amount) / (1000 if unit.lower() == "ms" else 1) + 60 * int(minutes or 0)
            # Waits past the cap are daily (TPD) limits; retrying within this run can't succeed.
            return secs + 1 if secs + 1 <= MAX_BACKOFF_S else None  # +1s: the hint is rounded down
        return min(2.0 ** attempt * 2, MAX_BACKOFF_S)
    if isinstance(err, TRANSIENT_ERRORS):
        return min(2.0 ** attempt, MAX_BACKOFF_S)
    # Bad generations: model emitted invalid JSON / schema-violating output. Retry right away.
    if isinstance(err, (OutputParserException, ValidationError, TruncatedOutput)):
        return 0.0
    if isinstance(err, BAD_REQUEST_ERRORS) and re.search(
        r"tool_use_failed|json_validate_failed|validation failed|Failed to parse", str(err)
    ):
        return 0.0
    return None


def normalize_quantity(ing: Ingredient) -> None:
    """Deterministic unit rules from the schema: count words -> each, bundle -> bunch."""
    q = ing.quantity
    if q.min is None:
        return
    if q.unit is None and q.qualitative and COUNT_WORD_RE.match(q.qualitative):
        q.unit, q.qualitative = "each", None
    elif q.unit in (None, "each") and BUNCH_WORD_RE.search(f"{q.qualitative or ''} {ing.raw_text}"):
        q.unit = "bunch"
        if q.qualitative and BUNCH_WORD_RE.search(q.qualitative):
            q.qualitative = None


def extract_recipe(title: str, raw_text: str, ingest_source: str | None) -> ExtractionResult:
    if not raw_text.strip():
        return ExtractionResult(status="not_a_recipe")
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Video title: {title}\n\nIngredient text:\n{raw_text}"),
    ]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = _invoke(0 if attempt == 1 else RETRY_TEMPERATURE, messages)
            break
        except Exception as err:
            delay = _retry_delay(err, attempt)
            if delay is None or attempt == MAX_ATTEMPTS:
                raise
            print(f"extract attempt {attempt}/{MAX_ATTEMPTS} failed ({type(err).__name__}); "
                  f"retry in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)
    if result.recipe:
        for ing in result.recipe.ingredients:
            normalize_quantity(ing)
            if ingest_source:
                ing.sources = [ingest_source]
    return result
