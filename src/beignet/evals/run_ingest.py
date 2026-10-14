"""Score the ingest ladder against the golden set.

Checks which rung produced the text and how many expected ingredient names
show up in it. Needs network (yt-dlp + recipe pages).

    uv run python -m beignet.evals.run_ingest [case_id ...]
"""
import json
import sys
from pathlib import Path

from beignet.ingest import ingest_video

GOLDEN = Path(__file__).parent / "golden"
def run_case(path: Path) -> dict:
    case = json.loads(path.read_text())
    expected_rung = case["expected_ingest_stopped_at"]
    got = ingest_video(case["url"])
    text = got["raw_text"].lower()
    names = [i["name"].lower() for i in case["expected"]["recipe"]["ingredients"]]
    # Loose match: any word (>3 chars) of the ingredient name appears in the text.
    hits = sum(any(w in text for w in n.split() if len(w) > 3) for n in names)
    return {
        "id": path.stem,
        "rung_ok": got["ingest_source"] == expected_rung,
        "expected": expected_rung,
        "got": got["ingest_source"],
        "recall": hits / len(names) if names else 1.0,
    }


def main() -> None:
    ids = set(sys.argv[1:])
    paths = [p for p in sorted(GOLDEN.glob("*.json")) if not ids or p.stem in ids]
    results = []
    for p in paths:
        try:
            r = run_case(p)
        except Exception as e:  # network / yt-dlp failures shouldn't kill the run
            r = {"id": p.stem, "rung_ok": False, "expected": "?", "got": f"error: {e}", "recall": 0.0}
        results.append(r)
        flag = "ok  " if r["rung_ok"] else "FAIL"
        print(f"{flag} {r['id']}  expected={r['expected']} got={r['got']} recall={r['recall']:.0%}")
    ok = sum(r["rung_ok"] for r in results)
    print(f"\nrung accuracy: {ok}/{len(results)}")


if __name__ == "__main__":
    main()
