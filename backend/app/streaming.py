"""Run the graph and turn its output into simple events for the browser."""
from collections.abc import Iterator

from app.graph.builder import STREAM_NODES


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else p.get("text", "") for p in content if isinstance(p, (str, dict)))
    return ""


def stream_graph(graph, inputs: dict) -> Iterator[dict]:
    """Yields: {"type": "status"|"reset"|"token", ...} and finally {"type": "final", "state": {...}}."""
    final: dict = {}
    for mode, data in graph.stream(inputs, stream_mode=["messages", "custom", "updates"]):
        if mode == "messages":
            chunk, meta = data
            if meta.get("langgraph_node") in STREAM_NODES:
                text = _text(chunk.content)
                if text:
                    yield {"type": "token", "text": text}
        elif mode == "custom":
            if isinstance(data, dict):
                yield data
        elif mode == "updates":
            for _node, update in data.items():
                if isinstance(update, dict):
                    final.update(update)
    yield {"type": "final", "state": final}
