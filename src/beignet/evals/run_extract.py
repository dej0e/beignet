"""Score LLM extraction against the golden set.

Runs ingest + extract per case, matches returned ingredients to expected ones
by name (one-to-one, best similarity first), then compares quantities.

    uv run python -m beignet.evals.run_extract [-v] [case_id ...]

Needs network, GROQ_API_KEY, and burns Groq tokens (rate limits are retried).
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from beignet.extract import extract_recipe
from beignet.ingest import ingest_video

GOLDEN = Path(__file__).parent / "golden"
NAME_THRESHOLD = 0.75
# Names may differ more when raw_text is the same line ("neutral oil" vs "neutral-flavoured oil").
SAME_LINE_NAME_THRESHOLD = 0.4
REL_TOL = 0.05


def norm(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())


def name_score(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:  # "chicken" vs "chicken thigh"
        return 0.85
    return SequenceMatcher(None, a, b).ratio()


def pair_score(e: dict, g: dict, pos_gap: float) -> float | None:
    """Match score for an expected/returned pair, or None if they can't be the same ingredient.

    Name similarity decides whether a pair is allowed. Same-name duplicates (salt in the marinade
    and in the sauce) are then told apart by raw_text, component, and position in the list.
    """
    name = name_score(e["name"], g["name"])
    same_line = norm(e["raw_text"]) == norm(g.get("raw_text", ""))
    if name < NAME_THRESHOLD and not (same_line and name >= SAME_LINE_NAME_THRESHOLD):
        return None
    line = 1.0 if same_line else SequenceMatcher(None, norm(e["raw_text"]), norm(g.get("raw_text", ""))).ratio()
    component = norm(e.get("component") or "") == norm(g.get("component") or "")
    return name + line + 0.3 * component - 0.05 * pos_gap  # position: tie-break only


def match_ingredients(expected: list[dict], got: list[dict]) -> list[tuple[int, int]]:
    """One-to-one (expected_idx, got_idx) pairs, best pair_score first."""
    scored = []
    for i, e in enumerate(expected):
        for j, g in enumerate(got):
            pos_gap = abs(i / max(len(expected), 1) - j / max(len(got), 1))
            score = pair_score(e, g, pos_gap)
            if score is not None:
                scored.append((score, i, j))
    scored.sort(reverse=True)
    used_e, used_g, pairs = set(), set(), []
    for _, i, j in scored:
        if i in used_e or j in used_g:
            continue
        used_e.add(i), used_g.add(j)
        pairs.append((i, j))
    return sorted(pairs)


def close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= max(0.01, REL_TOL * abs(a))


def quantity_ok(exp: dict, got: dict) -> bool:
    if exp.get("min") is None and exp.get("max") is None:  # qualitative: "to taste"
        return got.get("min") is None and got.get("max") is None
    return (close(exp.get("min"), got.get("min")) and close(exp.get("max"), got.get("max"))
            and exp.get("unit") == got.get("unit"))


def run_case(path: Path) -> dict:
    case = json.loads(path.read_text())
    exp_status = case["expected"]["status"]
    exp_ings = case["expected"].get("recipe", {}).get("ingredients", [])
    ing = ingest_video(case["url"])
    result = extract_recipe(ing["title"], ing["raw_text"], ing["ingest_source"])
    got_ings = [i.model_dump() for i in result.recipe.ingredients] if result.recipe else []

    pairs = match_ingredients(exp_ings, got_ings)
    qty_bad = [(exp_ings[i], got_ings[j]) for i, j in pairs
               if not quantity_ok(exp_ings[i].get("quantity", {}), got_ings[j]["quantity"])]
    matched_e = {i for i, _ in pairs}
    matched_g = {j for _, j in pairs}
    return {
        "id": path.stem,
        "status_ok": result.status == exp_status,
        "n_expected": len(exp_ings),
        "n_got": len(got_ings),
        "matched": len(pairs),
        "qty_ok": len(pairs) - len(qty_bad),
        "missing": [e["name"] for i, e in enumerate(exp_ings) if i not in matched_e],
        "extra": [g["name"] for j, g in enumerate(got_ings) if j not in matched_g],
        "qty_bad": qty_bad,
    }


def main() -> None:
    args = sys.argv[1:]
    verbose = "-v" in args
    ids = {a for a in args if a != "-v"}
    paths = [p for p in sorted(GOLDEN.glob("*.json")) if not ids or p.stem in ids]

    results, failed = [], []
    for p in paths:
        try:
            r = run_case(p)
        except Exception as e:  # retries exhausted or non-retryable
            failed.append(p.stem)
            print(f"ERR  {p.stem}  {type(e).__name__}: {str(e)[:200]}")
            continue
        results.append(r)
        print(f"{'ok  ' if r['status_ok'] else 'FAIL'} {r['id']}  expected={r['n_expected']} "
              f"got={r['n_got']} matched={r['matched']} qty_ok={r['qty_ok']}/{r['matched']}")
        if verbose:
            if r["missing"]:
                print(f"       missing: {r['missing']}")
            if r["extra"]:
                print(f"       extra:   {r['extra']}")
            for e, g in r["qty_bad"]:
                print(f"       qty {e['name']!r}: expected {e.get('quantity')} got {g['quantity']}")

    n_exp = sum(r["n_expected"] for r in results)
    n_got = sum(r["n_got"] for r in results)
    matched = sum(r["matched"] for r in results)
    qty_ok = sum(r["qty_ok"] for r in results)
    print(f"\ncases: {len(results)} scored, {len(failed)} errored {failed or ''}")
    if n_exp:
        print(f"recall (expected found by name): {matched}/{n_exp} = {matched / n_exp:.0%}")
        print(f"precision (returned that match):  {matched}/{n_got} = {matched / max(n_got, 1):.0%}")
        print(f"quantity accuracy (of matched):   {qty_ok}/{matched} = {qty_ok / max(matched, 1):.0%}")


if __name__ == "__main__":
    main()
