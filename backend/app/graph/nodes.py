"""The steps of the agent. Each node reads the state and returns the fields it changes."""
import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.clients import get_llm
from app.config import get_settings
from app.graph import prompts
from app.graph.state import GraphState
from app.retrieval import format_ref, search_hybrid

logger = logging.getLogger(__name__)


# ---------- structured outputs (what the LLM must return) ----------------------------

class Analysis(BaseModel):
    intent: Literal["legal", "smalltalk", "off_topic"] = Field(description="Kind of message")
    language: str = Field(description="English name of the user's language")
    search_query: str = Field(description="Standalone English search query")


class Grade(BaseModel):
    relevant_numbers: list[int] = Field(description="Numbers of the relevant excerpts")


class GroundingCheck(BaseModel):
    grounded: bool = Field(description="True if every claim is supported by the excerpts")
    issues: str = Field(description="Unsupported claims, or empty string")


# ---------- helpers -----------------------------------------------------------------------

def _emit(event: dict) -> None:
    """Send a live event (status / reset) to the browser. Ignored outside a graph run."""
    try:
        get_stream_writer()(event)
    except Exception:  # noqa: BLE001
        pass


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p if isinstance(p, str) else p.get("text", "") for p in content if isinstance(p, (str, dict))
        )
    return str(content)


def _structured(schema, messages):
    return get_llm().with_structured_output(schema).invoke(messages)


def _history_text(history: list[dict]) -> str:
    if not history:
        return "(none)"
    return "\n".join(f"{h['role']}: {h['content'][:500]}" for h in history[-6:])


def _history_messages(history: list[dict]):
    out = []
    for h in history[-4:]:
        text = h["content"][:1500]
        out.append(HumanMessage(content=text) if h["role"] == "user" else AIMessage(content=text))
    return out


def _context_block(chunks: list[dict], limit: int = 1500) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        title = f" - {c['title']}" if c.get("title") else ""
        parts.append(f"[{i}] {format_ref(c['act'], c.get('section_number'))}{title}\n{c['content'][:limit]}")
    return "\n\n".join(parts)


def build_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "n": i,
            "ref": format_ref(c["act"], c.get("section_number")),
            "act": c["act"],
            "section_number": c.get("section_number"),
            "title": c.get("title"),
            "page": c.get("page"),
            "snippet": c["content"][:400],
        }
        for i, c in enumerate(chunks, start=1)
    ]


def will_retry_generation(state: GraphState) -> bool:
    return state.get("verified") is False and state.get("generation_attempts", 0) <= get_settings().max_regenerations


# ---------- nodes -----------------------------------------------------------------------

def analyze(state: GraphState) -> dict:
    """Gate 1: is this a legal question? Also detects language and writes an English search query."""
    _emit({"type": "status", "step": "analyzing"})
    question = state["question"]
    target = state.get("target_language", "auto")
    try:
        a = _structured(
            Analysis,
            [
                SystemMessage(content=prompts.ANALYZE_SYSTEM),
                HumanMessage(
                    content=f"Chat history:\n{_history_text(state.get('history', []))}\n\nLatest user message:\n{question}"
                ),
            ],
        )
        intent = a.intent
        language = a.language.strip() or "the same language as the user's message"
        search_query = a.search_query.strip() or question
    except Exception:  # noqa: BLE001
        logger.exception("analyze failed; falling back to a plain legal search")
        intent, language, search_query = "legal", "the same language as the user's message", question
    if target and target != "auto":
        language = target
    return {
        "intent": intent,
        "language": language,
        "search_query": search_query,
        "retrieval_attempts": 0,
        "generation_attempts": 0,
        "issues": "",
        "verified": None,
        "sources": [],
    }


def route_after_analyze(state: GraphState) -> str:
    return "retrieve" if state.get("intent") == "legal" else "chitchat"


def retrieve(state: GraphState) -> dict:
    _emit({"type": "status", "step": "searching"})
    candidates = search_hybrid(state["search_query"], k=get_settings().retrieval_k)
    return {"candidates": candidates, "retrieval_attempts": state.get("retrieval_attempts", 0) + 1}


def grade(state: GraphState) -> dict:
    """Gate 2 (Corrective RAG): keep only excerpts that really help answer the question."""
    candidates = state.get("candidates", [])
    if not candidates:
        return {"relevant": []}
    _emit({"type": "status", "step": "checking"})
    try:
        g = _structured(
            Grade,
            [
                SystemMessage(content=prompts.GRADE_SYSTEM),
                HumanMessage(
                    content=f"Question: {state['search_query']}\n(original: {state['question']})\n\n"
                    f"Excerpts:\n{_context_block(candidates, limit=700)}"
                ),
            ],
        )
        keep = {n for n in g.relevant_numbers if 1 <= n <= len(candidates)}
        relevant = [c for i, c in enumerate(candidates, start=1) if i in keep][:6]
    except Exception:  # noqa: BLE001
        logger.exception("grade failed; using top results")
        relevant = candidates[:4]
    return {"relevant": relevant}


def route_after_grade(state: GraphState) -> str:
    if state.get("relevant"):
        return "generate"
    if state.get("retrieval_attempts", 0) <= get_settings().max_retrieval_retries:
        return "rewrite"
    return "no_answer"


def rewrite(state: GraphState) -> dict:
    try:
        resp = get_llm().invoke(
            [
                SystemMessage(content=prompts.REWRITE_SYSTEM),
                HumanMessage(content=f"Question: {state['question']}\nFailed query: {state['search_query']}"),
            ]
        )
        new_query = _text_of(resp.content).strip().strip('"').strip()
        if new_query:
            return {"search_query": new_query}
    except Exception:  # noqa: BLE001
        logger.exception("rewrite failed; keeping the old query")
    return {}


def generate(state: GraphState) -> dict:
    _emit({"type": "status", "step": "writing"})
    attempts = state.get("generation_attempts", 0)
    relevant = state["relevant"]
    system = prompts.GENERATE_SYSTEM.format(
        language=state.get("language", "English"), context=_context_block(relevant)
    )
    if attempts > 0 and state.get("issues"):
        system += prompts.RETRY_ADDENDUM.format(issues=state["issues"])
    messages = [SystemMessage(content=system), *_history_messages(state.get("history", [])), HumanMessage(content=state["question"])]
    resp = get_llm().invoke(messages)
    return {
        "answer": _text_of(resp.content).strip(),
        "generation_attempts": attempts + 1,
        "sources": build_sources(relevant),
    }


def check_grounded(state: GraphState) -> dict:
    """Gate 3 (Self-RAG): is every claim in the answer supported by the excerpts?"""
    _emit({"type": "status", "step": "verifying"})
    try:
        r = _structured(
            GroundingCheck,
            [
                SystemMessage(content=prompts.GROUNDED_SYSTEM),
                HumanMessage(
                    content=f"Excerpts:\n{_context_block(state['relevant'])}\n\nQuestion: {state['question']}\n\n"
                    f"Draft answer:\n{state['answer']}"
                ),
            ],
        )
    except Exception:  # noqa: BLE001
        logger.exception("grounding check failed; leaving answer unverified")
        return {"verified": None}
    update = {"verified": bool(r.grounded), "issues": r.issues.strip()}
    if not r.grounded and will_retry_generation({**state, **update}):
        _emit({"type": "reset"})  # tell the browser to clear the draft; a better one is coming
    return update


def route_after_check(state: GraphState) -> str:
    return "generate" if will_retry_generation(state) else "end"


def _short_reply(system_template: str, state: GraphState) -> dict:
    resp = get_llm().invoke(
        [
            SystemMessage(content=system_template.format(language=state.get("language", "English"))),
            HumanMessage(content=state["question"]),
        ]
    )
    return {"answer": _text_of(resp.content).strip(), "sources": [], "verified": None}


def chitchat(state: GraphState) -> dict:
    return _short_reply(prompts.CHITCHAT_SYSTEM, state)


def no_answer(state: GraphState) -> dict:
    return _short_reply(prompts.NO_ANSWER_SYSTEM, state)
