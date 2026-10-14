from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import beignet.nodes as nodes
from beignet.graph import build_graph, graph
from beignet.schema import ExtractionResult

RECIPE = ExtractionResult.model_validate({"status": "ok", "recipe": {"title": "t", "ingredients": [
    {"raw_text": "2 eggs", "name": "eggs", "sources": ["description"], "confidence": 0.9,
     "quantity": {"min": 2, "max": 2, "unit": "each"}},
    {"raw_text": "Salt to taste", "name": "salt", "sources": ["description"], "confidence": 0.9,
     "quantity": {"qualitative": "to taste"}},
]}})


def stub(monkeypatch, raw_text="2 eggs\nSalt to taste", result=RECIPE):
    monkeypatch.setattr(nodes, "ingest_video", lambda url: {
        "title": "t", "raw_text": raw_text, "ingest_source": "description" if raw_text else None,
        "source_url": url})
    monkeypatch.setattr(nodes, "extract_recipe", lambda title, text, source: result)


def test_exported_graph_has_no_checkpointer():
    assert graph.checkpointer is None


def test_review_interrupt_then_trim_and_approve(monkeypatch, capsys):
    stub(monkeypatch)
    g = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    paused = g.invoke({"url": "https://youtu.be/x"}, config)
    cart = paused["__interrupt__"][0].value["cart"]
    assert [c["name"] for c in cart] == ["eggs", "salt"]

    final = g.invoke(Command(resume={"approved": True, "cart": cart[:1]}), config)
    assert final["approved"] is True
    assert [c["name"] for c in final["cart"]] == ["eggs"]
    assert "Would send to Instacart" in capsys.readouterr().out


def test_no_recipe_path(monkeypatch, capsys):
    stub(monkeypatch, raw_text="", result=ExtractionResult(status="not_a_recipe"))
    final = build_graph(checkpointer=InMemorySaver()).invoke(
        {"url": "https://youtu.be/x"}, {"configurable": {"thread_id": "t2"}})
    assert final["status"] == "not_a_recipe"
    assert "No recipe found" in capsys.readouterr().out
