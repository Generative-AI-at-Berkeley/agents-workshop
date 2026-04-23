from __future__ import annotations

from langchain_core.messages import AIMessage

from graph.m6.state import M6State

MAX_ORCHESTRATOR_ROUNDS = 3


def route_action(state: M6State) -> str:
	last_msg = state["messages"][-1]
	if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
		return "respond"
	for tc in last_msg.tool_calls:
		if tc["name"] == "search_events":
			return "search_pipeline"
	return "direct_lookup"


def should_stop(state: M6State) -> str:
	if state.get("done", False):
		return "end"
	if state.get("tool_rounds", 0) >= MAX_ORCHESTRATOR_ROUNDS:
		return "end"
	return "continue"
