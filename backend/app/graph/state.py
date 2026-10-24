from typing import TypedDict


class GraphState(TypedDict, total=False):
    # inputs
    question: str
    history: list[dict]        # [{"role": "user"|"assistant", "content": "..."}]
    target_language: str       # "auto" or a language name picked in the UI
    # set by analyze
    intent: str                # legal | smalltalk | off_topic
    language: str              # language the answer is written in
    search_query: str          # standalone English query
    # retrieval
    candidates: list[dict]
    relevant: list[dict]
    retrieval_attempts: int
    # generation
    answer: str
    generation_attempts: int
    issues: str
    verified: bool | None
    sources: list[dict]
