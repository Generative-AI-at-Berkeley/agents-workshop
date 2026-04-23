from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.m4.conditions import should_retry
from graph.m4.nodes import amanage_scouts, aplan, areview, asynthesize, manage_scouts, plan, review, synthesize
from graph.m4.state import M4State


def _wire(builder):
	builder.add_edge(START, "plan")
	builder.add_edge("plan", "manage_scouts")
	builder.add_edge("manage_scouts", "synthesize")
	builder.add_edge("synthesize", "review")
	builder.add_conditional_edges("review", should_retry, {"end": END, "retry": "plan"})


def build_graph():
	builder = StateGraph(M4State)
	builder.add_node("plan", plan)
	builder.add_node("manage_scouts", manage_scouts)
	builder.add_node("synthesize", synthesize)
	builder.add_node("review", review)
	_wire(builder)
	return builder.compile(checkpointer=MemorySaver())


def build_async_graph():
	builder = StateGraph(M4State)
	builder.add_node("plan", aplan)
	builder.add_node("manage_scouts", amanage_scouts)
	builder.add_node("synthesize", asynthesize)
	builder.add_node("review", areview)
	_wire(builder)
	return builder.compile()


graph = build_graph()
