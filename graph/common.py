from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog
import yaml
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq

from config.settings import get_settings
from observability import generation_context, span_context
from schemas.nightout import NightOutRequest

log = structlog.get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = _PROJECT_ROOT / "agents"
CONFIG_DIR = _PROJECT_ROOT / "config"

MAX_TOOL_ROUNDS = 5


def _load_agent_prompt(agent_name: str) -> str:
	return (AGENTS_DIR / f"{agent_name}.md").read_text()


def _load_model_config(agent_name: str) -> dict:
	with open(CONFIG_DIR / "models.yaml") as f:
		cfg = yaml.safe_load(f)
	return cfg["agents"][agent_name]


def _build_llm(agent_name: str) -> ChatGroq:
	model_cfg = _load_model_config(agent_name)
	settings = get_settings()
	return ChatGroq(model=model_cfg["model"], api_key=settings.GROQ_API_KEY, temperature=0.7)


def _get_agent_tools(agent_name: str) -> list[Any]:
	from tools.registry import get_tools_for_agent

	return get_tools_for_agent(agent_name)


def _tools_to_openai_spec(tools: list[Any]) -> list[dict]:
	return [t.to_langchain_tool() for t in tools]


async def _execute_tool_calls(tool_calls: list[dict], tools: list[Any]) -> list[ToolMessage]:
	tool_map = {t.name: t for t in tools}
	results = []
	for tc in tool_calls:
		name = tc["name"]
		args = tc.get("args", {})
		tool = tool_map.get(name)
		if not tool:
			results.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tc["id"]))
			continue
		with span_context(name=f"tool.{name}", input=args) as span:
			result = await tool.run(**args)
			span.update(output=result.model_dump())
		content = json.dumps(result.data) if result.success else f"Error: {result.error}"
		results.append(ToolMessage(content=content, tool_call_id=tc["id"]))
	return results


def get_request(state: dict) -> NightOutRequest:
	r = state["request"]
	if isinstance(r, dict):
		return NightOutRequest(**r)
	return r


def strip_json_fences(text: str) -> str:
	text = text.strip()
	m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
	if m:
		return m.group(1).strip()
	return text


def call_agent_sync(agent_name: str, user_msg: str) -> str:
	system_prompt = _load_agent_prompt(agent_name)
	model_cfg = _load_model_config(agent_name)
	llm = _build_llm(agent_name)
	messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

	with generation_context(name=f"agent.{agent_name}", model=model_cfg["model"], input=user_msg) as gen:
		response = llm.invoke(messages)
		gen.update(output=response.content)

	log.info("agent_complete", agent=agent_name, response_length=len(response.content))
	return response.content


async def call_agent(agent_name: str, user_msg: str) -> str:
	system_prompt = _load_agent_prompt(agent_name)
	model_cfg = _load_model_config(agent_name)
	llm = _build_llm(agent_name)
	messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

	with generation_context(name=f"agent.{agent_name}", model=model_cfg["model"], input=user_msg) as gen:
		response = await llm.ainvoke(messages)
		gen.update(output=response.content)

	log.info("agent_complete", agent=agent_name, response_length=len(response.content))
	return response.content


async def call_agent_with_tools(agent_name: str, user_msg: str) -> str:
	system_prompt = _load_agent_prompt(agent_name)
	model_cfg = _load_model_config(agent_name)
	llm = _build_llm(agent_name)
	tools = _get_agent_tools(agent_name)

	if not tools:
		return await call_agent(agent_name, user_msg)

	tool_specs = _tools_to_openai_spec(tools)
	llm_with_tools = llm.bind_tools(tool_specs)
	messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

	for round_num in range(MAX_TOOL_ROUNDS):
		with generation_context(
			name=f"agent.{agent_name}.round_{round_num}", model=model_cfg["model"], input=user_msg
		) as gen:
			response: AIMessage = await llm_with_tools.ainvoke(messages)
			gen.update(output=response.content)

		messages.append(response)

		if not response.tool_calls:
			break

		log.info("tool_calls", agent=agent_name, round=round_num, tools=[tc["name"] for tc in response.tool_calls])
		tool_messages = await _execute_tool_calls(response.tool_calls, tools)
		messages.extend(tool_messages)

	log.info("agent_complete", agent=agent_name, response_length=len(response.content), rounds=round_num + 1)
	return response.content


def call_agent_sync_with_tools(agent_name: str, user_msg: str) -> str:
	import asyncio

	return asyncio.get_event_loop().run_until_complete(call_agent_with_tools(agent_name, user_msg))
