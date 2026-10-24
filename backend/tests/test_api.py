"""API tests against a real Postgres (needs schema.sql applied). Fake login + fake graph."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
import app.main as main

USER_A = CurrentUser(id=str(uuid.uuid4()), email="a@example.com")
USER_B = CurrentUser(id=str(uuid.uuid4()), email="b@example.com")


class FakeGraph:
    def stream(self, inputs, stream_mode=None):
        self.last_inputs = inputs
        yield "custom", {"type": "status", "step": "analyzing"}
        from langchain_core.messages import AIMessageChunk
        yield "messages", (AIMessageChunk(content="Hello "), {"langgraph_node": "generate"})
        yield "messages", (AIMessageChunk(content="ignored"), {"langgraph_node": "grade"})
        yield "messages", (AIMessageChunk(content="world"), {"langgraph_node": "generate"})
        yield "updates", {"generate": {"answer": "Hello world", "sources": [{"n": 1, "ref": "BNS Section 103"}], "verified": True}}


@pytest.fixture
def client():
    try:
        main.init_pool()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no test database: {e}")
    main.app.state.graph = FakeGraph()
    main.app.dependency_overrides[get_current_user] = lambda: USER_A
    main.check_rate_limit = lambda uid: None
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def parse_sse(text: str) -> list[dict]:
    return [json.loads(block[len("data: "):]) for block in text.strip().split("\n\n") if block.startswith("data: ")]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_login():
    main.app.dependency_overrides.clear()
    c = TestClient(main.app)
    assert c.get("/conversations").status_code == 401
    assert c.post("/chat", json={"message": "hi"}).status_code == 401


def test_chat_creates_conversation_streams_and_saves(client):
    r = client.post("/chat", json={"message": "What is murder punishment?", "language": "Hindi"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert events[0]["type"] == "meta"
    cid = events[0]["conversation_id"]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello world"
    done = events[-1]
    assert done["type"] == "done" and done["verified"] is True and done["sources"][0]["ref"] == "BNS Section 103"
    assert main.app.state.graph.last_inputs["target_language"] == "Hindi"

    msgs = client.get(f"/conversations/{cid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "Hello world" and msgs[1]["sources"][0]["n"] == 1

    # follow-up message sends history to the graph
    client.post("/chat", json={"message": "and bail?", "conversation_id": cid})
    hist = main.app.state.graph.last_inputs["history"]
    assert [h["role"] for h in hist] == ["user", "assistant"]

    convs = client.get("/conversations").json()
    assert any(c["id"] == cid for c in convs)


def test_other_users_cannot_see_or_delete_chat(client):
    cid = parse_sse(client.post("/chat", json={"message": "private question"}).text)[0]["conversation_id"]
    main.app.dependency_overrides[get_current_user] = lambda: USER_B
    assert client.get(f"/conversations/{cid}/messages").status_code == 404
    assert client.delete(f"/conversations/{cid}").status_code == 404
    assert client.post("/chat", json={"message": "x", "conversation_id": cid}).status_code == 404
    assert all(c["id"] != cid for c in client.get("/conversations").json())
    main.app.dependency_overrides[get_current_user] = lambda: USER_A
    assert client.delete(f"/conversations/{cid}").status_code == 204
    assert client.get(f"/conversations/{cid}/messages").status_code == 404


def test_validation(client):
    assert client.post("/chat", json={"message": "   "}).status_code == 422
    assert client.post("/chat", json={"message": "hi", "language": "Klingon"}).status_code == 422
    assert client.post("/chat", json={"message": "x" * 1600}).status_code == 422
    assert client.get("/conversations/not-a-uuid/messages").status_code == 422


def test_graph_error_is_reported_not_crashed(client):
    class Boom:
        def stream(self, *a, **k):
            raise RuntimeError("OpenAI down")
            yield
    main.app.state.graph = Boom()
    events = parse_sse(client.post("/chat", json={"message": "hi"}).text)
    assert events[-1]["type"] == "error"
