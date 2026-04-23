from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.m2.conditions import should_retry
from graph.m2.nodes import aplan, areview, ascout, asynthesize, plan, review, scout, synthesize
from graph.m2.state import M2State


def _wire(builder):
	builder.add_edge(START, "plan")
	builder.add_edge("plan", "scout")
	builder.add_edge("scout", "synthesize")
	builder.add_edge("synthesize", "review")
	builder.add_conditional_edges("review", should_retry, {"end": END, "retry": "plan"})


def build_graph():
	builder = StateGraph(M2State)
	builder.add_node("plan", plan)
	builder.add_node("scout", scout)
	builder.add_node("synthesize", synthesize)
	builder.add_node("review", review)
	_wire(builder)
	return builder.compile(checkpointer=MemorySaver())


def build_async_graph():
	builder = StateGraph(M2State)
	builder.add_node("plan", aplan)
	builder.add_node("scout", ascout)
	builder.add_node("synthesize", asynthesize)
	builder.add_node("review", areview)
	_wire(builder)
	return builder.compile()


graph = build_graph()
