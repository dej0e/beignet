import pytest

import beignet.llm as llm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ["BEIGNET_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "GROQ_REASONING_EFFORT",
              "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_REASONING_EFFORT"]:
        monkeypatch.delenv(k, raising=False)
    llm.structured_llm.cache_clear()
    yield
    llm.structured_llm.cache_clear()


def test_default_provider_is_groq():
    cfg = llm.provider_config()
    assert (cfg.name, cfg.reasoning_effort) == ("groq", "low")


def test_provider_env_overrides(monkeypatch):
    monkeypatch.setenv("BEIGNET_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("OPENROUTER_REASONING_EFFORT", "")
    cfg = llm.provider_config()
    assert (cfg.name, cfg.model, cfg.reasoning_effort) == ("openrouter", "openai/gpt-oss-120b", None)


def test_api_key_not_in_repr(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secret")
    assert "gsk_secret" not in repr(llm.provider_config())


def test_missing_key_and_unknown_provider(monkeypatch):
    monkeypatch.setenv("BEIGNET_PROVIDER", "openrouter")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        llm.structured_llm(0)
    monkeypatch.setenv("BEIGNET_PROVIDER", "bogus")
    with pytest.raises(RuntimeError, match="unknown BEIGNET_PROVIDER"):
        llm.provider_config()


def test_strict_schema_shape():
    def walk(node):
        if isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object" and "properties" in node:
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    schema = llm.llm_schema(strict=True)
    walk(schema)
    assert schema["$defs"]["Quantity"]["properties"]["unit"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    # long lists last, so small models don't lose track of nesting
    assert list(schema["properties"])[-1] == "recipe"
    assert list(schema["$defs"]["Recipe"]["properties"])[-1] == "ingredients"
