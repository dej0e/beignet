from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

from beignet.extract import extract_recipe
from beignet.ingest import ingest_video


class State(TypedDict, total=False):
    url: str
    title: str
    raw_text: str
    ingest_source: str | None
    source_url: str | None
    status: str
    ingredients: list[dict]
    cart: list[dict]
    approved: bool

def ingest(state: State):
    return ingest_video(state["url"])

def extract(state: State):
    result = extract_recipe(state.get("title", ""), state["raw_text"], state.get("ingest_source"))
    if result.status == "not_a_recipe" or not result.recipe:
        return {"status": "not_a_recipe"}
    return {
        "status": result.status,
        "ingredients": [i.model_dump() for i in result.recipe.ingredients],
    }

def route_after_extract(state: State) -> Literal["plan", "no_recipe"]:
    return "no_recipe" if state["status"] == "not_a_recipe" else "plan"

def plan(state: State):
    return {"cart": [{"item": i["raw_text"], "name": i["name"], "quantity": i["quantity"],
                      "optional": i["optional"], "action": "buy"} for i in state["ingredients"]]}

def review(state: State):
    # Pauses the graph; whatever you resume with is returned here
    decision = interrupt({"cart": state["cart"]})
    return {"cart": decision.get("cart", state["cart"]),
            "approved": decision["approved"]}

def route_after_review(state: State) -> Literal["fulfill", "__end__"]:
    return "fulfill" if state["approved"] else END

def fulfill(state: State):
    print("Would send to Instacart:", state["cart"])
    return {}

def no_recipe(state: State):
    print("No recipe found in this video.")
    return {}

builder = StateGraph(State)
for name, fn in [("ingest", ingest), ("extract", extract), ("plan", plan),
                 ("review", review), ("fulfill", fulfill), ("no_recipe", no_recipe)]:
    builder.add_node(name, fn)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "extract")
builder.add_conditional_edges("extract", route_after_extract)
builder.add_edge("plan", "review")
builder.add_conditional_edges("review", route_after_review)
builder.add_edge("fulfill", END)
builder.add_edge("no_recipe", END)

graph = builder.compile(checkpointer=InMemorySaver())

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "run-1"}}

    result = graph.invoke({"url": "https://youtube.com/watch?v=..."}, config)

    if "__interrupt__" in result:
        cart = result["__interrupt__"][0].value["cart"]
        print("\nProposed cart:")
        for i, item in enumerate(cart, 1):
            print(f"  {i}. {item['item']}")

        answer = input("\nApprove? [y = yes / n = no / or numbers to remove, e.g. 3]: ").strip().lower()

        if answer == "y":
            decision = {"approved": True}
        elif answer == "n":
            decision = {"approved": False}
        else:
            remove = {int(x) for x in answer.replace(",", " ").split() if x.isdigit()}
            kept = [item for i, item in enumerate(cart, 1) if i not in remove]
            decision = {"approved": True, "cart": kept}

        final = graph.invoke(Command(resume=decision), config)
        print("\nDone.")
    else:
        print("No interruption occurred.")