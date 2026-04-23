from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class M6State(TypedDict):
	messages: Annotated[list, add_messages]
	tool_rounds: int
	done: bool
	current_query: str
	search_plan: list[dict]
	raw_results: list[dict]
	validated_results: list[dict]
