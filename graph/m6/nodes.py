from __future__ import annotations

import asyncio
import json

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from graph.common import (
	_build_llm,
	_get_agent_tools,
	_load_agent_prompt,
	_load_model_config,
	_tools_to_openai_spec,
	strip_json_fences,
)
from graph.m6.state import M6State
from observability import generation_context, span_context
from tools.events import EventSearch, TicketLookup
from tools.firecrawl import FirecrawlSearch

log = structlog.get_logger(__name__)

_FIRECRAWL_SEMAPHORE = asyncio.Semaphore(3)


def _trim_history(messages: list) -> list:
	last_human_idx = 0
	for i, m in enumerate(messages):
		if isinstance(m, HumanMessage):
			last_human_idx = i

	trimmed = []
	for i, m in enumerate(messages):
		if i >= last_human_idx:
			trimmed.append(m)
		elif isinstance(m, ToolMessage):
			continue
		elif isinstance(m, AIMessage) and m.tool_calls:
			summary = m.content or "[searched for events]"
			trimmed.append(AIMessage(content=summary))
		else:
			trimmed.append(m)
	return trimmed


def _get_orchestrator_system() -> SystemMessage:
	return SystemMessage(content=_load_agent_prompt("deep_orchestrator"))


def _build_orchestrator_llm():
	llm = _build_llm("deep_orchestrator")
	tools = _get_agent_tools("deep_orchestrator")
	tool_specs = _tools_to_openai_spec(tools)
	return llm.bind_tools(tool_specs), tools


def _extract_search_params(tool_calls: list[dict]) -> dict:
	for tc in tool_calls:
		if tc["name"] == "search_events":
			args = tc.get("args", {})
			return {
				"query": args.get("query", ""),
				"city": args.get("city", ""),
				"date": args.get("date", ""),
			}
	return {"query": "", "city": "", "date": ""}


async def orchestrator(state: M6State) -> dict:
	llm_with_tools, _tools = _build_orchestrator_llm()
	model_cfg = _load_model_config("deep_orchestrator")

	messages = list(state["messages"])
	if not messages or not isinstance(messages[0], SystemMessage):
		messages.insert(0, _get_orchestrator_system())

	llm_messages = _trim_history(messages)
	round_num = state.get("tool_rounds", 0)

	with generation_context(
		name=f"agent.orchestrator.round_{round_num}", model=model_cfg["model"], input=str(llm_messages[-1].content)
	) as gen:
		response: AIMessage = await llm_with_tools.ainvoke(llm_messages)
		gen.update(output=response.content)

	new_messages: list = [response]
	update: dict = {"messages": new_messages, "tool_rounds": round_num + 1}

	if response.tool_calls:
		params = _extract_search_params(response.tool_calls)
		if params["query"]:
			query_parts = [params["query"]]
			if params["city"]:
				query_parts.append(params["city"])
			if params["date"]:
				query_parts.append(params["date"])
			update["current_query"] = " ".join(query_parts)
		log.info("orchestrator_tools", round=round_num, tools=[tc["name"] for tc in response.tool_calls])
	else:
		update["done"] = True
		log.info("orchestrator_respond", round=round_num, length=len(response.content))

	return update


def orchestrator_sync(state: M6State) -> dict:
	return asyncio.run(_orchestrator_sync_inner(state))


async def _orchestrator_sync_inner(state: M6State) -> dict:
	return await orchestrator(state)


async def search_planner(state: M6State) -> dict:
	model_cfg = _load_model_config("search_planner")
	llm = _build_llm("search_planner")
	prompt = _load_agent_prompt("search_planner")

	current_query = state.get("current_query", "")
	user_msg = f"Find events for: {current_query}"

	with generation_context(name="agent.search_planner", model=model_cfg["model"], input=user_msg) as gen:
		response = await llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=user_msg)])
		gen.update(output=response.content)

	try:
		plan = json.loads(strip_json_fences(response.content))
		if isinstance(plan, dict):
			plan = plan.get("queries", plan.get("searches", [plan]))
		if not isinstance(plan, list):
			plan = [{"query": current_query, "strategy": "fallback", "tool": "event_search"}]
	except (json.JSONDecodeError, KeyError):
		log.warning("search_planner_parse_failed", content=response.content[:200])
		plan = [{"query": current_query, "strategy": "fallback", "tool": "event_search"}]

	log.info("search_plan", query=current_query, plan_size=len(plan))
	return {"search_plan": plan[:8]}


def search_planner_sync(state: M6State) -> dict:
	return asyncio.run(search_planner(state))


async def search_executor(state: M6State) -> dict:
	plan = state.get("search_plan", [])
	if not plan:
		return {"raw_results": []}

	event_tool = EventSearch()
	firecrawl_tool = FirecrawlSearch()
	seen_urls: set[str] = set()
	all_results: list[dict] = []

	async def _run_search(item: dict) -> list[dict]:
		query = item.get("query", "")
		tool_name = item.get("tool", "event_search")

		async with _FIRECRAWL_SEMAPHORE:
			with span_context(name=f"search.{item.get('strategy', 'unknown')}", input=query) as span:
				if tool_name == "firecrawl_search":
					result = await firecrawl_tool.run(query=query, limit=5)
				else:
					city = ""
					for c in ["San Francisco", "Bay Area", "Los Angeles", "New York", "Chicago", "Miami", "Austin", "Denver", "Seattle", "Portland"]:
						if c.lower() in query.lower():
							city = c
							break
					result = await event_tool.run(city=city or "unknown", query=query)

				span.update(output={"success": result.success, "count": len(result.data) if result.data else 0})

		if not result.success or not result.data:
			return []
		if isinstance(result.data, list):
			return result.data
		return []

	batch_results = await asyncio.gather(*[_run_search(item) for item in plan], return_exceptions=True)

	for batch in batch_results:
		if isinstance(batch, Exception):
			log.warning("search_executor_error", error=str(batch))
			continue
		for entry in batch:
			url = entry.get("url", "")
			if url and url not in seen_urls:
				seen_urls.add(url)
				all_results.append(entry)

	log.info("search_executor_done", total_results=len(all_results), searches=len(plan))
	return {"raw_results": all_results[:15]}


def search_executor_sync(state: M6State) -> dict:
	return asyncio.run(search_executor(state))


async def validator(state: M6State) -> dict:
	raw = state.get("raw_results", [])
	if not raw:
		return {"validated_results": []}

	ticket_tool = TicketLookup()
	to_validate = raw[:8]

	async def _validate_one(entry: dict) -> dict | None:
		url = entry.get("url", "")
		if not url:
			return None
		async with _FIRECRAWL_SEMAPHORE:
			with span_context(name="validate", input=url) as span:
				result = await ticket_tool.run(url=url)
				span.update(output={"success": result.success})
		if not result.success:
			return None
		content = result.data.get("content", "") if isinstance(result.data, dict) else ""
		if not content or len(content) < 50:
			return None
		if len(content) > 3000:
			content = content[:3000] + "\n\n[truncated]"
		return {**entry, "details": content, "validated": True}

	results = await asyncio.gather(*[_validate_one(e) for e in to_validate], return_exceptions=True)
	validated = [r for r in results if isinstance(r, dict)]

	log.info("validator_done", input_count=len(to_validate), validated_count=len(validated))
	return {"validated_results": validated}


def validator_sync(state: M6State) -> dict:
	return asyncio.run(validator(state))


async def synthesizer(state: M6State) -> dict:
	model_cfg = _load_model_config("search_synthesizer")
	llm = _build_llm("search_synthesizer")
	prompt = _load_agent_prompt("search_synthesizer")

	validated = state.get("validated_results", [])
	raw = state.get("raw_results", [])
	current_query = state.get("current_query", "")

	if validated:
		events_json = json.dumps(validated, indent=2, default=str)
	elif raw:
		events_json = json.dumps(raw[:10], indent=2, default=str)
		events_json += "\n\nNOTE: These results could not be validated via scraping. Present them with caveats."
	else:
		events_json = "[]"

	user_msg = f"User's query: {current_query}\n\nSearch results ({len(validated)} validated, {len(raw)} raw):\n{events_json}"

	with generation_context(name="agent.search_synthesizer", model=model_cfg["model"], input=user_msg[:500]) as gen:
		response = await llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=user_msg)])
		gen.update(output=response.content)

	pending_tool_calls = []
	for msg in reversed(state["messages"]):
		if isinstance(msg, AIMessage) and msg.tool_calls:
			pending_tool_calls = msg.tool_calls
			break

	new_messages: list = []
	for tc in pending_tool_calls:
		summary = f"Searched {len(raw)} sources, validated {len(validated)} events"
		new_messages.append(ToolMessage(content=summary, tool_call_id=tc["id"]))

	new_messages.append(AIMessage(content=response.content))

	log.info("synthesizer_done", validated=len(validated), raw=len(raw), response_len=len(response.content))
	return {
		"messages": new_messages,
		"done": True,
		"search_plan": [],
		"raw_results": [],
		"validated_results": [],
	}


def synthesizer_sync(state: M6State) -> dict:
	return asyncio.run(synthesizer(state))


async def tool_executor(state: M6State) -> dict:
	last_msg = state["messages"][-1]
	if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
		return {"done": True}

	results: list = []
	for tc in last_msg.tool_calls:
		if tc["name"] == "lookup_event":
			url = tc.get("args", {}).get("url", "")
			with span_context(name="tool.lookup_event", input=url) as span:
				tool = TicketLookup()
				result = await tool.run(url=url)
				span.update(output=result.model_dump())
			content = json.dumps(result.data) if result.success else f"Error: {result.error}"
			results.append(ToolMessage(content=content, tool_call_id=tc["id"]))
		else:
			results.append(ToolMessage(content=f"Unknown tool: {tc['name']}", tool_call_id=tc["id"]))

	return {"messages": results}


def tool_executor_sync(state: M6State) -> dict:
	return asyncio.run(tool_executor(state))
