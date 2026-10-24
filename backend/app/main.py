"""FastAPI app: login-protected chat API with streaming answers (Server-Sent Events)."""
import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from psycopg.types.json import Jsonb

from app.auth import CurrentUser, check_rate_limit, get_current_user
from app.config import get_settings
from app.db import close_pool, execute, fetch_all, fetch_one, init_pool
from app.graph.builder import build_graph
from app.schemas import ChatRequest, ConversationOut, MessageOut
from app.streaming import stream_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nyay")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    app.state.graph = build_graph()
    logger.info("Nyay AI backend ready")
    yield
    close_pool()


app = FastAPI(title="Nyay AI", version="1.0.0", lifespan=lifespan)

_s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_s.cors_origins,
    allow_origin_regex=_s.cors_origin_regex or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: CurrentUser = Depends(get_current_user)):
    return fetch_all(
        """SELECT id, title, created_at, updated_at FROM conversations
           WHERE user_id = %s::uuid ORDER BY updated_at DESC LIMIT 100""",
        (user.id,),
    )


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)):
    _require_owner(conversation_id, user)
    return fetch_all(
        """SELECT id, role, content, sources, verified, created_at FROM messages
           WHERE conversation_id = %s ORDER BY id""",
        (conversation_id,),
    )


@app.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser = Depends(get_current_user)):
    row = fetch_one(
        "DELETE FROM conversations WHERE id = %s AND user_id = %s::uuid RETURNING id",
        (conversation_id, user.id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Chat not found.")


def _require_owner(conversation_id: uuid.UUID, user: CurrentUser) -> None:
    row = fetch_one(
        "SELECT 1 AS ok FROM conversations WHERE id = %s AND user_id = %s::uuid",
        (conversation_id, user.id),
    )
    if row is None:  # same answer for "missing" and "someone else's": never leak existence
        raise HTTPException(status_code=404, detail="Chat not found.")


@app.post("/chat")
def chat(req: ChatRequest, user: CurrentUser = Depends(get_current_user)):
    s = get_settings()
    if len(req.message) > s.max_message_chars:
        raise HTTPException(status_code=422, detail=f"Please keep your question under {s.max_message_chars} characters.")
    check_rate_limit(user.id)

    # --- everything that can fail with a normal HTTP error happens BEFORE streaming starts
    if req.conversation_id:
        _require_owner(req.conversation_id, user)
        conversation_id = req.conversation_id
        history_rows = fetch_all(
            """SELECT role, content FROM messages WHERE conversation_id = %s
               ORDER BY id DESC LIMIT %s""",
            (conversation_id, s.history_messages),
        )
        history = list(reversed(history_rows))
    else:
        title = req.message[:60] + ("…" if len(req.message) > 60 else "")
        row = fetch_one(
            "INSERT INTO conversations (user_id, title) VALUES (%s::uuid, %s) RETURNING id",
            (user.id, title),
        )
        assert row is not None
        conversation_id = row["id"]
        history = []

    execute(
        "INSERT INTO messages (conversation_id, user_id, role, content) VALUES (%s, %s::uuid, 'user', %s)",
        (conversation_id, user.id, req.message),
    )

    graph = app.state.graph
    inputs = {"question": req.message, "history": history, "target_language": req.language}

    def event_stream() -> Iterator[str]:
        yield sse({"type": "meta", "conversation_id": str(conversation_id)})
        final: dict = {}
        try:
            for event in stream_graph(graph, inputs):
                if event["type"] == "final":
                    final = event["state"]
                else:
                    yield sse(event)
        except Exception:  # noqa: BLE001
            logger.exception("Chat failed")
            yield sse({"type": "error", "message": "Something went wrong while answering. Please try again."})
            return

        answer = (final.get("answer") or "").strip()
        if not answer:
            yield sse({"type": "error", "message": "No answer was produced. Please try again."})
            return

        sources = final.get("sources") or []
        verified = final.get("verified")
        message_id = None
        try:
            saved = fetch_one(
                """INSERT INTO messages (conversation_id, user_id, role, content, sources, verified)
                   VALUES (%s, %s::uuid, 'assistant', %s, %s, %s) RETURNING id""",
                (conversation_id, user.id, answer, Jsonb(sources), verified),
            )
            message_id = saved["id"] if saved else None
            execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
        except Exception:  # noqa: BLE001
            logger.exception("Could not save the answer")
        yield sse({"type": "done", "message_id": message_id, "sources": sources, "verified": verified})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
