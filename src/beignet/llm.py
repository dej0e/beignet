"""LLM providers: per-provider config and structured-output clients.

BEIGNET_PROVIDER picks the provider ("groq" default, or "openrouter"). Each provider reads its
own env vars, so switching providers doesn't carry a model id over to a provider without it:

    groq:        GROQ_API_KEY,       GROQ_MODEL,       GROQ_REASONING_EFFORT,       GROQ_MAX_OUTPUT_TOKENS
    openrouter:  OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_REASONING_EFFORT, OPENROUTER_MAX_OUTPUT_TOKENS
"""
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import get_args

import groq
import openai
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from beignet.schema import ExtractionResult, Unit

load_dotenv()

# Output budget covers hidden reasoning tokens too; a 36-line recipe needs ~3k tokens of JSON alone.
DEFAULT_MAX_OUTPUT_TOKENS = 8192

# Error types across both SDKs, for the caller's retry policy.
RATE_LIMIT_ERRORS = (groq.RateLimitError, openai.RateLimitError)
TRANSIENT_ERRORS = (groq.APIConnectionError, groq.InternalServerError,
                    openai.APIConnectionError, openai.InternalServerError)
BAD_REQUEST_ERRORS = (groq.BadRequestError, openai.BadRequestError)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None = field(repr=False)  # keep secrets out of logs and tracebacks
    model: str
    reasoning_effort: str | None  # None: don't send a reasoning parameter
    max_output_tokens: int

    @classmethod
    def from_env(cls, name: str, default_model: str, default_effort: str | None) -> "ProviderConfig":
        prefix = name.upper()
        effort = os.getenv(f"{prefix}_REASONING_EFFORT", default_effort or "") or None
        return cls(
            name=name,
            api_key=os.getenv(f"{prefix}_API_KEY"),
            model=os.getenv(f"{prefix}_MODEL", default_model),
            reasoning_effort=effort,
            max_output_tokens=int(os.getenv(f"{prefix}_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)),
        )

    def require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(f"provider {self.name!r} needs {self.name.upper()}_API_KEY")
        return self.api_key


def groq_config() -> ProviderConfig:
    return ProviderConfig.from_env("groq", default_model="openai/gpt-oss-20b", default_effort="low")


def openrouter_config() -> ProviderConfig:
    return ProviderConfig.from_env("openrouter", default_model="openai/gpt-oss-20b", default_effort="low")


def llm_schema(strict: bool) -> dict:
    """ExtractionResult JSON schema as sent to the model.

    `unit` is loosened from the enum to any string: smaller models invent units ("pods",
    "pieces") and fail the whole response on them. extract.coerce_units maps the string back
    onto the Unit enum before Pydantic validation.

    strict: the form strict decoding accepts - every property in `required` and
    `additionalProperties: false`. Optional fields are already nullable (anyOf ... null), so the
    model emits null for them; defaults are dropped because strict mode rejects them.
    """
    schema = {"title": "ExtractionResult", **ExtractionResult.model_json_schema()}
    unit = schema["$defs"]["Quantity"]["properties"]["unit"]
    unit["anyOf"] = [{"type": "string"}, {"type": "null"}]
    unit["description"] += f" Allowed units: {', '.join(get_args(Unit))}."

    def fix(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)
        return node
    return fix(schema) if strict else schema


def _groq(cfg: ProviderConfig, temperature: float):
    # Groq only accepts reasoning_effort on reasoning models (gpt-oss)
    extra = {"reasoning_effort": cfg.reasoning_effort} if cfg.reasoning_effort else {}
    llm = ChatGroq(model=cfg.model, temperature=temperature, max_tokens=cfg.max_output_tokens,
                   api_key=cfg.require_key(), **extra)
    # strict: constrained decoding, so the output always matches the schema. Without it,
    # gpt-oss-20b drifts on long outputs (string "null", missing fields, misplaced keys).
    return llm.with_structured_output(llm_schema(strict=True), method="json_schema", strict=True,
                                      include_raw=True)


def _openrouter(cfg: ProviderConfig, temperature: float):
    body: dict = {
        # only route to providers that honor response_format, so the schema is enforced
        "provider": {"require_parameters": True},
    }
    if cfg.reasoning_effort:
        body["reasoning"] = {"effort": cfg.reasoning_effort}
    llm = ChatOpenAI(model=cfg.model, temperature=temperature, max_tokens=cfg.max_output_tokens,
                     api_key=cfg.require_key(), base_url="https://openrouter.ai/api/v1", extra_body=body)
    # A plain JSON schema (non-strict) instead of the Pydantic class: the class makes the OpenAI SDK
    # demand strict mode, which many OpenRouter providers reject. The caller validates the dict.
    return llm.with_structured_output(llm_schema(strict=False), method="json_schema", strict=False,
                                      include_raw=True)


PROVIDERS = {
    "groq": (groq_config, _groq),
    "openrouter": (openrouter_config, _openrouter),
}


def provider_config() -> ProviderConfig:
    name = os.getenv("BEIGNET_PROVIDER", "groq")
    if name not in PROVIDERS:
        raise RuntimeError(f"unknown BEIGNET_PROVIDER={name!r}; use one of {sorted(PROVIDERS)}")
    return PROVIDERS[name][0]()


@lru_cache
def structured_llm(temperature: float):
    """Runnable returning {"raw", "parsed", "parsing_error"} for ExtractionResult.

    include_raw is set so callers can see finish_reason and reject truncated output.
    """
    cfg = provider_config()
    return PROVIDERS[cfg.name][1](cfg, temperature)
