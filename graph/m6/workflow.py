from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.m6.conditions import route_action, should_stop
from graph.m6.nodes import (
	orchestrator,
	orchestrator_sync,
	search_executor,
	search_executor_sync,
	search_planner,
	search_planner_sync,
	synthesizer,
	synthesizer_sync,
	tool_executor,
	tool_executor_sync,
	validator,
	validator_sync,
)
from graph.m6.state import M6State


def _wire(builder: StateGraph) -> None:
	builder.add_edge(START, "orchestrator")

	builder.add_conditional_edges(
		"orchestrator",
		route_action,
		{"search_pipeline": "search_planner", "direct_lookup": "tool_executor", "respond": END},
	)

	builder.add_edge("search_planner", "search_executor")
	builder.add_edge("search_executor", "validator")
	builder.add_edge("validator", "synthesizer")

	builder.add_conditional_edges("synthesizer", should_stop, {"end": END, "continue": "orchestrator"})
	builder.add_conditional_edges("tool_executor", should_stop, {"end": END, "continue": "orchestrator"})


def build_graph():
	builder = StateGraph(M6State)
	builder.add_node("orchestrator", orchestrator_sync)
	builder.add_node("search_planner", search_planner_sync)
	builder.add_node("search_executor", search_executor_sync)
	builder.add_node("validator", validator_sync)
	builder.add_node("synthesizer", synthesizer_sync)
	builder.add_node("tool_executor", tool_executor_sync)
	_wire(builder)
	return builder.compile(checkpointer=MemorySaver())


def build_async_graph():
	builder = StateGraph(M6State)
	builder.add_node("orchestrator", orchestrator)
	builder.add_node("search_planner", search_planner)
	builder.add_node("search_executor", search_executor)
	builder.add_node("validator", validator)
	builder.add_node("synthesizer", synthesizer)
	builder.add_node("tool_executor", tool_executor)
	_wire(builder)
	return builder.compile(checkpointer=MemorySaver())


graph = build_graph()
