from __future__ import annotations

import asyncio
import json
import time

import structlog

from graph.common import (
	call_agent,
	call_agent_sync,
	call_agent_with_tools,
	call_agent_sync_with_tools,
	get_request,
	strip_json_fences,
)
from graph.m5.state import M5State
from observability import span_context
from schemas.nightout import Itinerary

log = structlog.get_logger(__name__)


def _plan_msg(state: M5State) -> str:
	request = get_request(state)
	feedback = state.get("review_feedback", "")
	user_msg = f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\nGroup size: {request.group_size}\n"
	if request.notes:
		user_msg += f"Notes: {request.notes}\n"
	if feedback:
		user_msg += f"\nPrevious attempt was rejected. Feedback: {feedback}\nAdjust your plan accordingly.\n"
	return user_msg


def _manager_msg(state: M5State) -> str:
	request = get_request(state)
	return (
		f"City: {request.city}\nVibe: {request.vibe}\nDate: {request.date}\n\n"
		f"PLAN:\n{state['plan']}\n\n"
		f"Assign scouts to research this plan."
	)


def _parse_assignments(result: str) -> list[dict]:
	raw = json.loads(strip_json_fences(result))
	return raw.get("assignments", raw) if isinstance(raw, dict) else raw


async def _dispatch_scout(scout_name: str, task: str, use_tools: bool) -> str:
	call_fn = call_agent_with_tools if use_tools else call_agent
	with span_context(name=f"subagent.{scout_name}", input=task) as span:
		result = await call_fn(scout_name, task)
		span.update(output=result)
	return f"## {scout_name}\n{result}"


async def _dispatch_scouts_parallel(assignments: list[dict], use_tools: bool = False) -> str:
	start = time.monotonic()
	tasks = [_dispatch_scout(a["scout"], a["task"], use_tools) for a in assignments]
	reports = await asyncio.gather(*tasks)
	elapsed = time.monotonic() - start
	log.info("parallel_scouts_complete", count=len(assignments), elapsed_s=round(elapsed, 2))
	return "\n\n".join(reports)


def _dispatch_scouts_sequential(assignments: list[dict], use_tools: bool = False) -> str:
	start = time.monotonic()
	call_fn = call_agent_sync_with_tools if use_tools else call_agent_sync
	reports = []
	for a in assignments:
		scout_name = a["scout"]
		task = a["task"]
		with span_context(name=f"subagent.{scout_name}", input=task) as span:
			result = call_fn(scout_name, task)
			span.update(output=result)
		reports.append(f"## {scout_name}\n{result}")
	elapsed = time.monotonic() - start
	log.info("sequential_scouts_complete", count=len(assignments), elapsed_s=round(elapsed, 2))
	return "\n\n".join(reports)


def _merge_msg(state: M5State) -> str:
	return f"Merge and deduplicate the following scout reports:\n\n{state['raw_research']}"


def _synthesize_msg(state: M5State) -> str:
	request = get_request(state)
	return (
		f"City: {request.city}\nDate: {request.date}\n"
		f"Vibe: {request.vibe}\nGroup size: {request.group_size}\n\n"
		f"ROUGH PLAN:\n{state['plan']}\n\n"
		f"VENUE RESEARCH:\n{state['merged_research']}\n\n"
		f"Produce the final JSON itinerary."
	)


def _review_msg(state: M5State) -> str:
	itinerary = state["itinerary"]
	if isinstance(itinerary, dict):
		data = itinerary
	else:
		data = itinerary.model_dump()
	return f"Review this itinerary:\n\n{json.dumps(data, indent=2)}"


def _parse_review(result: str, state: M5State) -> dict:
	passed = result.strip().startswith("APPROVED")
	feedback = "" if passed else result.replace("NEEDS_REVISION:", "").strip()
	return {"review_passed": passed, "review_feedback": feedback, "attempts": state.get("attempts", 0) + 1}


# --- Sync (VizLang) — scouts run sequentially ---


def plan(state: M5State) -> dict:
	return {"plan": call_agent_sync("planner", _plan_msg(state))}


def manage_scouts(state: M5State) -> dict:
	result = call_agent_sync("manager", _manager_msg(state))
	assignments = _parse_assignments(result)
	research = _dispatch_scouts_sequential(assignments, use_tools=False)
	return {"scout_assignments": assignments, "raw_research": research}


def merge(state: M5State) -> dict:
	return {"merged_research": call_agent_sync("merge", _merge_msg(state))}


def synthesize(state: M5State) -> dict:
	result = strip_json_fences(call_agent_sync("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


def review(state: M5State) -> dict:
	result = call_agent_sync("reviewer", _review_msg(state))
	return _parse_review(result, state)


# --- Async (CLI / API) — scouts run in parallel ---


async def aplan(state: M5State) -> dict:
	return {"plan": await call_agent("planner", _plan_msg(state))}


async def amanage_scouts(state: M5State) -> dict:
	result = await call_agent("manager", _manager_msg(state))
	assignments = _parse_assignments(result)
	research = await _dispatch_scouts_parallel(assignments, use_tools=False)
	return {"scout_assignments": assignments, "raw_research": research}


async def amerge(state: M5State) -> dict:
	return {"merged_research": await call_agent("merge", _merge_msg(state))}


async def asynthesize(state: M5State) -> dict:
	result = strip_json_fences(await call_agent("synthesizer", _synthesize_msg(state)))
	return {"itinerary": Itinerary.model_validate_json(result)}


async def areview(state: M5State) -> dict:
	result = await call_agent("reviewer", _review_msg(state))
	return _parse_review(result, state)
