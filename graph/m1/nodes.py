from __future__ import annotations

from graph.common import call_agent, call_agent_sync, get_request, strip_json_fences
from graph.m1.state import M1State
from schemas.nightout import Itinerary


def _build_msg(state: M1State) -> str:
	request = get_request(state)
	user_msg = f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\nGroup size: {request.group_size}\n"
	if request.notes:
		user_msg += f"Notes: {request.notes}\n"
	return user_msg


def plan_night(state: M1State) -> dict:
	result = strip_json_fences(call_agent_sync("planner_v1", _build_msg(state)))
	itinerary = Itinerary.model_validate_json(result)
	return {"itinerary": itinerary}


async def aplan_night(state: M1State) -> dict:
	result = strip_json_fences(await call_agent("planner_v1", _build_msg(state)))
	itinerary = Itinerary.model_validate_json(result)
	return {"itinerary": itinerary}
