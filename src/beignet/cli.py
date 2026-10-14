"""Interactive run: ingest a video, review the proposed cart, approve or trim it.

    uv run beignet <youtube-url>
"""
import sys
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from beignet.graph import build_graph


def ask_decision(cart: list[dict]) -> dict:
    print("\nProposed cart:")
    for i, item in enumerate(cart, 1):
        print(f"  {i}. {item['item']}")

    answer = input("\nApprove? [y = yes / n = no / or numbers to remove, e.g. 3]: ").strip().lower()

    if answer == "y":
        return {"approved": True}
    if answer == "n":
        return {"approved": False}
    remove = {int(x) for x in answer.replace(",", " ").split() if x.isdigit()}
    kept = [item for i, item in enumerate(cart, 1) if i not in remove]
    return {"approved": True, "cart": kept}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: beignet <youtube-url>")
    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke({"url": sys.argv[1]}, config)

    if "__interrupt__" in result:
        decision = ask_decision(result["__interrupt__"][0].value["cart"])
        graph.invoke(Command(resume=decision), config)
        print("\nDone.")
    else:
        print("No interruption occurred.")


if __name__ == "__main__":
    main()
