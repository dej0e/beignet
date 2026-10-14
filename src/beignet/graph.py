"""Graph wiring. `graph` is what langgraph.json exposes to `langgraph dev` / LangGraph Studio."""
from langgraph.graph import StateGraph, START, END

from beignet.nodes import (extract, fulfill, ingest, no_recipe, plan, review, route_after_extract,
                           route_after_review)
from beignet.state import State


def build_graph(checkpointer=None):
    """Compile the graph. The LangGraph server brings its own persistence, so the exported
    `graph` has no checkpointer; local callers (cli.py) pass one for interrupt/resume."""
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

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
