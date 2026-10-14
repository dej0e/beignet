from unittest.mock import MagicMock

import httpx
import openai
import pytest

import beignet.extract as ex
from beignet.schema import Ingredient


def ingredient(raw, mn, mx, unit, qual):
    return Ingredient(raw_text=raw, name="x", sources=[], confidence=0.9,
                      quantity={"min": mn, "max": mx, "unit": unit, "qualitative": qual})


@pytest.mark.parametrize("written, unit, qual", [
    ("tbsp", "tbsp", None), ("Tablespoons", "tbsp", None), ("tbsps", "tbsp", None),
    ("cups", "cup", None), ("grams", "g", None), ("lbs", "lb", None), ("fl oz", "fl_oz", None),
    ("Cloves", "clove", None), ("pods", "each", None), ("pieces", "each", None), ("pcs", "each", None),
    ("bundle", "bunch", None), ("sprigs", None, "sprigs"), ("quarts", None, "quarts"), ("", None, None),
])
def test_coerce_units(written, unit, qual):
    data = {"recipe": {"ingredients": [{"quantity": {"unit": written, "qualitative": None}}]}}
    q = ex.coerce_units(data)["recipe"]["ingredients"][0]["quantity"]
    assert (q["unit"], q["qualitative"]) == (unit, qual)


@pytest.mark.parametrize("raw, mn, mx, unit, qual, want_unit, want_qual", [
    ("5-7 pods green cardamom", 5, 7, None, "pods", "each", None),
    ("1 large bundle cilantro, chopped", 1, 1, "each", "large bundle, chopped", "bunch", None),
    ("3 thyme sprigs", 3, 3, None, "sprigs", None, "sprigs"),
    ("Salt to taste", None, None, None, "to taste", None, "to taste"),
])
def test_normalize_quantity(raw, mn, mx, unit, qual, want_unit, want_qual):
    i = ingredient(raw, mn, mx, unit, qual)
    ex.normalize_quantity(i)
    assert (i.quantity.unit, i.quantity.qualitative) == (want_unit, want_qual)


def rate_limit(message="rate limited", headers=None):
    req = httpx.Request("POST", "https://example")
    return openai.RateLimitError(message, response=httpx.Response(429, request=req, headers=headers), body=None)


def test_retry_delay():
    assert ex._retry_delay(rate_limit(headers={"retry-after": "4"}), 1) == 5.0
    assert ex._retry_delay(rate_limit("Please try again in 1.83s."), 1) == pytest.approx(2.83)
    assert ex._retry_delay(rate_limit("Please try again in 7m12.5s."), 1) is None  # daily limit
    assert ex._retry_delay(rate_limit(), 2) == 8.0
    assert ex._retry_delay(ex.TruncatedOutput("x"), 1) == 0.0
    assert ex._retry_delay(ValueError("x"), 1) is None


def fake_llm(parsed, finish_reason="stop"):
    llm = MagicMock()
    llm.invoke.return_value = {"raw": MagicMock(response_metadata={"finish_reason": finish_reason}),
                               "parsing_error": None, "parsed": parsed}
    return llm


PARSED = {"status": "ok", "recipe": {"title": "t", "ingredients": [
    {"raw_text": "5-7 pods green cardamom", "name": "cardamom", "sources": [], "confidence": 0.9,
     "quantity": {"min": 5, "max": 7, "unit": "pods", "qualitative": None}}]}}


def test_extract_recipe_validates_coerces_and_tags_source(monkeypatch):
    monkeypatch.setattr(ex, "structured_llm", lambda t: fake_llm(PARSED))
    r = ex.extract_recipe("t", "5-7 pods green cardamom", "description")
    ing = r.recipe.ingredients[0]
    assert ing.quantity.unit == "each"
    assert ing.sources == ["description"]


def test_truncated_output_is_retried_then_raised(monkeypatch):
    llm = fake_llm(PARSED, finish_reason="length")
    monkeypatch.setattr(ex, "structured_llm", lambda t: llm)
    with pytest.raises(ex.TruncatedOutput):
        ex.extract_recipe("t", "text", "description")
    assert llm.invoke.call_count == ex.MAX_ATTEMPTS


def test_empty_text_skips_llm(monkeypatch):
    monkeypatch.setattr(ex, "structured_llm", lambda t: pytest.fail("LLM should not be called"))
    assert ex.extract_recipe("t", "  ", None).status == "not_a_recipe"
