"""Tests the agent's control flow with a fake LLM and fake search (no API calls)."""
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.graph.builder import build_graph
from app.graph.nodes import Analysis, Grade, GroundingCheck
from app.streaming import stream_graph

CHUNK = {"id": 1, "act": "BNS", "section_number": "103", "title": "Punishment for murder",
         "content": "Whoever commits murder shall be punished with death or imprisonment for life.", "page": 5}


class FakeLLM(GenericFakeChatModel):
    structured: dict = {}

    def with_structured_output(self, schema, **kwargs):
        queue = self.structured[schema]
        return RunnableLambda(lambda _msgs: queue.pop(0))


def make_fake(texts, analysis=None, grades=None, checks=None):
    return FakeLLM(
        messages=iter([AIMessage(content=t) for t in texts]),
        structured={
            Analysis: list(analysis or []),
            Grade: list(grades or []),
            GroundingCheck: list(checks or []),
        },
    )


def run(monkeypatch, fake, search_results, question="What is the punishment for murder?", target="auto"):
    calls = {"search": 0}

    def fake_search(query, k=8):
        calls["search"] += 1
        return list(search_results)

    monkeypatch.setattr("app.graph.nodes.get_llm", lambda: fake)
    monkeypatch.setattr("app.graph.nodes.search_hybrid", fake_search)
    events = list(stream_graph(build_graph(), {"question": question, "history": [], "target_language": target}))
    return events, calls


def test_happy_path_streams_and_verifies(monkeypatch):
    fake = make_fake(
        ["Murder is punished with death or life imprisonment [1]."],
        analysis=[Analysis(intent="legal", language="English", search_query="punishment for murder")],
        grades=[Grade(relevant_numbers=[1])],
        checks=[GroundingCheck(grounded=True, issues="")],
    )
    events, calls = run(monkeypatch, fake, [CHUNK])
    tokens = "".join(e["text"] for e in events if e["type"] == "token")
    final = events[-1]["state"]
    assert tokens.strip() == "Murder is punished with death or life imprisonment [1]."
    assert final["verified"] is True
    assert final["sources"][0]["ref"] == "BNS Section 103"
    assert [e["step"] for e in events if e["type"] == "status"] == ["analyzing", "searching", "checking", "writing", "verifying"]
    assert not any(e["type"] == "reset" for e in events)
    assert calls["search"] == 1


def test_off_topic_goes_to_chitchat_without_search(monkeypatch):
    fake = make_fake(
        ["I can only help with BNS, BNSS and the Constitution."],
        analysis=[Analysis(intent="off_topic", language="English", search_query="best pizza")],
    )
    events, calls = run(monkeypatch, fake, [CHUNK], question="best pizza near me?")
    assert calls["search"] == 0
    assert "".join(e["text"] for e in events if e["type"] == "token").startswith("I can only help")
    assert events[-1]["state"]["sources"] == []


def test_ungrounded_answer_is_regenerated_once_with_reset(monkeypatch):
    fake = make_fake(
        ["Bad draft [1].", "Good draft [1]."],
        analysis=[Analysis(intent="legal", language="English", search_query="murder")],
        grades=[Grade(relevant_numbers=[1])],
        checks=[GroundingCheck(grounded=False, issues="invented a fine amount"),
                GroundingCheck(grounded=True, issues="")],
    )
    events, _ = run(monkeypatch, fake, [CHUNK])
    kinds = [e["type"] for e in events]
    assert kinds.count("reset") == 1
    # tokens after the reset belong to the second draft
    after = "".join(e["text"] for e in events[kinds.index("reset"):] if e["type"] == "token")
    assert after.strip() == "Good draft [1]."
    final = events[-1]["state"]
    assert final["answer"] == "Good draft [1]."
    assert final["verified"] is True
    assert final["generation_attempts"] == 2


def test_still_ungrounded_after_retry_stops_and_flags(monkeypatch):
    fake = make_fake(
        ["Draft one [1].", "Draft two [1]."],
        analysis=[Analysis(intent="legal", language="English", search_query="murder")],
        grades=[Grade(relevant_numbers=[1])],
        checks=[GroundingCheck(grounded=False, issues="x"), GroundingCheck(grounded=False, issues="y")],
    )
    events, _ = run(monkeypatch, fake, [CHUNK])
    final = events[-1]["state"]
    assert final["verified"] is False
    assert final["generation_attempts"] == 2  # no endless loop


def test_nothing_relevant_rewrites_once_then_gives_up(monkeypatch):
    fake = make_fake(
        ["a better query", "Sorry, I could not find a matching provision."],
        analysis=[Analysis(intent="legal", language="Hindi", search_query="weird")],
        grades=[Grade(relevant_numbers=[]), Grade(relevant_numbers=[])],
    )
    events, calls = run(monkeypatch, fake, [CHUNK])
    assert calls["search"] == 2
    final = events[-1]["state"]
    assert final["answer"].startswith("Sorry")
    assert final["sources"] == []
    # the rewritten query is not streamed to the user
    assert "a better query" not in "".join(e["text"] for e in events if e["type"] == "token")


def test_language_override_wins(monkeypatch):
    fake = make_fake(
        ["ok"],
        analysis=[Analysis(intent="smalltalk", language="English", search_query="hi")],
    )
    events, _ = run(monkeypatch, fake, [], question="hi", target="Tamil")
    assert events[-1]["state"]["language"] == "Tamil"


def test_analyze_failure_falls_back_to_legal_search(monkeypatch):
    fake = make_fake(["Answer [1]."], grades=[Grade(relevant_numbers=[1])], checks=[GroundingCheck(grounded=True, issues="")])
    fake.structured[Analysis] = []  # pop from empty list -> raises inside analyze
    events, calls = run(monkeypatch, fake, [CHUNK])
    assert calls["search"] == 1
    assert events[-1]["state"]["answer"] == "Answer [1]."
