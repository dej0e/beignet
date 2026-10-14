import copy
import json
import random
from pathlib import Path

import pytest

from evals.run_extract import match_ingredients, quantity_ok

GOLDEN = Path(__file__).parent.parent / "evals" / "golden"
CASES = sorted(p.stem for p in GOLDEN.glob("*.json"))


def ing(raw, name, comp=None):
    return {"raw_text": raw, "name": name, "component": comp}


@pytest.mark.parametrize("case_id", CASES)
def test_golden_matches_shuffled_self(case_id):
    expected = json.loads((GOLDEN / f"{case_id}.json").read_text())["expected"]["recipe"]["ingredients"]
    got = copy.deepcopy(expected)
    for g in got:
        g["component"] = None  # the model may not fill components
    order = list(range(len(got)))
    random.Random(case_id).shuffle(order)

    pairs = match_ingredients(expected, [got[k] for k in order])

    assert len(pairs) == len(expected)
    for i, j in pairs:
        e, g = expected[i], expected[order[j]]
        assert (e["raw_text"], e["name"]) == (g["raw_text"], g["name"])


def test_same_name_across_versions_pairs_by_raw_text():
    expected = [ing("1 large Onion", "onion", "30 minute"), ing("2 large onions", "onions", "3 hour")]
    got = [ing("2 large onions", "onion"), ing("1 large Onion", "Onion")]
    assert match_ingredients(expected, got) == [(0, 1), (1, 0)]


def test_duplicate_lines_pair_by_component():
    line = "1 tsp cooking salt / kosher salt"
    expected = [ing(line, "cooking salt", "marinade"), ing(line, "cooking salt", "sauce")]
    got = [ing(line, "kosher salt", "sauce"), ing(line, "cooking salt", "marinade")]
    assert match_ingredients(expected, got) == [(0, 1), (1, 0)]


def test_same_line_allows_looser_name():
    line = "3 tbsp neutral-flavoured oil"
    assert match_ingredients([ing(line, "neutral oil")], [ing(line, "neutral-flavoured oil")]) == [(0, 0)]


def test_unrelated_names_do_not_match():
    assert match_ingredients([ing("1 tsp salt", "salt")], [ing("2 eggs", "eggs")]) == []


def test_quantity_ok():
    assert quantity_ok({"min": 2, "max": 3, "unit": "tbsp"}, {"min": 2.0, "max": 3.0, "unit": "tbsp"})
    assert not quantity_ok({"min": 1, "max": 1, "unit": "tsp"}, {"min": 1.0, "max": 1.0, "unit": "tbsp"})
    assert quantity_ok({"min": None, "max": None, "qualitative": "to taste"},
                       {"min": None, "max": None, "unit": None, "qualitative": "to taste"})
