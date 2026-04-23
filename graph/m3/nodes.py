from __future__ import annotations

import json

from graph.common import (
	call_agent,
	call_agent_sync,
	call_agent_with_tools,
	call_agent_sync_with_tools,
	get_request,
	strip_json_fences,
)
from graph.m3.state import M3State
from schemas.nightout import Itinerary


def _plan_msg(state: M3State) -> str:
	request = get_request(state)
	feedback = state.get("review_feedback", "")
	user_msg = f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\nGroup size: {request.group_size}\n"
	if request.notes:
		user_msg += f"Notes: {request.notes}\n"
	if feedback:
		user_msg += f"\nPrevious attempt was rejected. Feedback: {feedback}\nAdjust your plan accordingly.\n"
	return user_msg


def _scout_msg(state: M3State) -> str:
	request = get_request(state)
	return (
		f"Research the following night out plan for {request.city}:\n\n"
		f"{state['plan']}\n\n"
		f"Use your search and scrape tools to find real, current information about each venue. "
		f"Verify addresses, hours, cover charges, and upcoming events. "
		f"Provide detailed info for each stop."
	)


def _synthesize_msg(state: M3State) -> str:
	request = get_request(state)
	return (
		f"City: {request.city}\nDate: {request.date}\n"
		f"Vibe: {request.vibe}\nGroup size: {request.group_size}\n\n"
		f"ROUGH PLAN:\n{state['plan']}\n\n"
		f"VENUE RESEARCH:\n{state['raw_research']}\n\n"
		f"Produce the final JSON itinerary."
	)


def _review_msg(state: M3State) -> str:
	itinerary = state["itinerary"]
	if isinstance(itinerary, dict):
		data = itinerary
	else:
		data = itinerary.model_dump()
	return f"Review this itinerary:\n\n{json.dumps(data, indent=2)}"


def _parse_review(result: str, state: M3State) -> dict:
	passed = result.strip().startswith("APPROVED")
	feedback = "" if passed else result.replace("NEEDS_REVISION:", "").strip()
	return {"review_passed": passed, "review_feedback": feedback, "attempts": state.get("attempts", 0) + 1}


# --- Sync (VizLang) ---


def plan(state: M3State) -> dict:
	return {"plan": call_agent_sync("planner", _plan_msg(state))}


def scout(state: M3State) -> dict:
	return {"raw_research": call_agent_sync_with_tools("scout", _scout_msg(state))}


def synthesize(state: M3State) -> dict:
	result = strip_json_fences(call_agent_sync("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


def review(state: M3State) -> dict:
	result = call_agent_sync("reviewer", _review_msg(state))
	return _parse_review(result, state)


# --- Async (CLI / API) ---


async def aplan(state: M3State) -> dict:
	return {"plan": await call_agent("planner", _plan_msg(state))}


async def ascout(state: M3State) -> dict:
	return {"raw_research": await call_agent_with_tools("scout", _scout_msg(state))}


async def asynthesize(state: M3State) -> dict:
	result = strip_json_fences(await call_agent("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


async def areview(state: M3State) -> dict:
	result = await call_agent("reviewer", _review_msg(state))
	return _parse_review(result, state)
