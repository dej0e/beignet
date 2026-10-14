from typing import TypedDict


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
