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
from graph.m4.state import M4State
from observability import span_context
from schemas.nightout import Itinerary


def _plan_msg(state: M4State) -> str:
	request = get_request(state)
	feedback = state.get("review_feedback", "")
	user_msg = f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\nGroup size: {request.group_size}\n"
	if request.notes:
		user_msg += f"Notes: {request.notes}\n"
	if feedback:
		user_msg += f"\nPrevious attempt was rejected. Feedback: {feedback}\nAdjust your plan accordingly.\n"
	return user_msg


def _manager_msg(state: M4State) -> str:
	request = get_request(state)
	return (
		f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\n\n"
		f"PLAN:\n{state['plan']}\n\n"
		f"Assign scouts to research this plan."
	)


def _parse_assignments(result: str) -> list[dict]:
	raw = json.loads(strip_json_fences(result))
	return raw.get("assignments", raw) if isinstance(raw, dict) else raw


def _dispatch_scouts_sequential(assignments: list[dict], use_tools: bool = False) -> str:
	call_fn = call_agent_sync_with_tools if use_tools else call_agent_sync
	reports = []
	for a in assignments:
		scout_name = a["scout"]
		task = a["task"]
		with span_context(name=f"subagent.{scout_name}", input=task) as span:
			result = call_fn(scout_name, task)
			span.update(output=result)
		reports.append(f"## {scout_name}\n{result}")
	return "\n\n".join(reports)


async def _dispatch_scouts_sequential_async(assignments: list[dict], use_tools: bool = False) -> str:
	call_fn = call_agent_with_tools if use_tools else call_agent
	reports = []
	for a in assignments:
		scout_name = a["scout"]
		task = a["task"]
		with span_context(name=f"subagent.{scout_name}", input=task) as span:
			result = await call_fn(scout_name, task)
			span.update(output=result)
		reports.append(f"## {scout_name}\n{result}")
	return "\n\n".join(reports)


def _synthesize_msg(state: M4State) -> str:
	request = get_request(state)
	return (
		f"City: {request.city}\nDate: {request.date}\n"
		f"Vibe: {request.vibe}\nGroup size: {request.group_size}\n\n"
		f"ROUGH PLAN:\n{state['plan']}\n\n"
		f"VENUE RESEARCH:\n{state['raw_research']}\n\n"
		f"Produce the final JSON itinerary."
	)


def _review_msg(state: M4State) -> str:
	itinerary = state["itinerary"]
	if isinstance(itinerary, dict):
		data = itinerary
	else:
		data = itinerary.model_dump()
	return f"Review this itinerary:\n\n{json.dumps(data, indent=2)}"


def _parse_review(result: str, state: M4State) -> dict:
	passed = result.strip().startswith("APPROVED")
	feedback = "" if passed else result.replace("NEEDS_REVISION:", "").strip()
	return {"review_passed": passed, "review_feedback": feedback, "attempts": state.get("attempts", 0) + 1}


# --- Sync (VizLang) ---


def plan(state: M4State) -> dict:
	return {"plan": call_agent_sync("planner", _plan_msg(state))}


def manage_scouts(state: M4State) -> dict:
	result = call_agent_sync("manager", _manager_msg(state))
	assignments = _parse_assignments(result)
	research = _dispatch_scouts_sequential(assignments, use_tools=False)
	return {"scout_assignments": assignments, "raw_research": research}


def synthesize(state: M4State) -> dict:
	result = strip_json_fences(call_agent_sync("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


def review(state: M4State) -> dict:
	result = call_agent_sync("reviewer", _review_msg(state))
	return _parse_review(result, state)


# --- Async (CLI / API) ---


async def aplan(state: M4State) -> dict:
	return {"plan": await call_agent("planner", _plan_msg(state))}


async def amanage_scouts(state: M4State) -> dict:
	result = await call_agent("manager", _manager_msg(state))
	assignments = _parse_assignments(result)
	research = await _dispatch_scouts_sequential_async(assignments, use_tools=False)
	return {"scout_assignments": assignments, "raw_research": research}


async def asynthesize(state: M4State) -> dict:
	result = strip_json_fences(await call_agent("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


async def areview(state: M4State) -> dict:
	result = await call_agent("reviewer", _review_msg(state))
	return _parse_review(result, state)
