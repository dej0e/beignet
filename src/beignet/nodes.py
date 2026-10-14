"""Graph nodes and routers. Kept thin: the work lives in ingest.py / extract.py."""
from typing import Literal

from langgraph.graph import END
from langgraph.types import interrupt

from beignet.extract import extract_recipe
from beignet.ingest import ingest_video
from beignet.state import State


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
