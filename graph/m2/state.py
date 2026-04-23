from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from schemas.nightout import Itinerary, NightOutRequest


class M2State(TypedDict):
	request: NightOutRequest
	messages: Annotated[list, add_messages]
	plan: str
	raw_research: str
	itinerary: Itinerary | None
	review_passed: bool
	review_feedback: str
	attempts: int
