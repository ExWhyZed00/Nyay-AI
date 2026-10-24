from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import GraphState

# Nodes whose LLM tokens are shown to the user as they are typed
STREAM_NODES = {"generate", "chitchat", "no_answer"}


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("analyze", nodes.analyze)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("grade", nodes.grade)
    g.add_node("rewrite", nodes.rewrite)
    g.add_node("generate", nodes.generate)
    g.add_node("check_grounded", nodes.check_grounded)
    g.add_node("chitchat", nodes.chitchat)
    g.add_node("no_answer", nodes.no_answer)

    g.add_edge(START, "analyze")
    g.add_conditional_edges("analyze", nodes.route_after_analyze, {"retrieve": "retrieve", "chitchat": "chitchat"})
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade", nodes.route_after_grade, {"generate": "generate", "rewrite": "rewrite", "no_answer": "no_answer"}
    )
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate", "check_grounded")
    g.add_conditional_edges("check_grounded", nodes.route_after_check, {"generate": "generate", "end": END})
    g.add_edge("chitchat", END)
    g.add_edge("no_answer", END)
    return g.compile()
