from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.m1.nodes import aplan_night, plan_night
from graph.m1.state import M1State


def build_graph():
	builder = StateGraph(M1State)
	builder.add_node("plan_night", plan_night)
	builder.add_edge(START, "plan_night")
	builder.add_edge("plan_night", END)
	return builder.compile(checkpointer=MemorySaver())


def build_async_graph():
	builder = StateGraph(M1State)
	builder.add_node("plan_night", aplan_night)
	builder.add_edge(START, "plan_night")
	builder.add_edge("plan_night", END)
	return builder.compile()


graph = build_graph()
