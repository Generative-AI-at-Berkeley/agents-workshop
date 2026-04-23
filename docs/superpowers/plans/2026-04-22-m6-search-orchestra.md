# M6 Multi-Agent Search Orchestra Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-agent ReAct deep agent with a multi-agent search pipeline that eliminates hallucination, searches intelligently, validates results, and distributes LLM load across Groq models.

**Architecture:** Orchestrator (ReAct, 2 tools) routes to a deterministic pipeline: Search Planner (LLM) -> Search Executor (parallel Firecrawl) -> Validator (parallel scrape) -> Synthesizer (LLM). Three LLM calls on three different Groq models per search turn = no TPM collision.

**Tech Stack:** LangGraph StateGraph, Groq (llama-4-scout, llama-3.1-8b, qwen3-32b), Firecrawl API, httpx, asyncio, structlog, Pydantic v2

---

## File Structure

**Create:**
- `agents/deep_orchestrator.md` — Orchestrator prompt (replaces deep_agent.md)
- `agents/search_planner.md` — Query decomposition prompt
- `agents/search_synthesizer.md` — Results presenter prompt
- `tests/test_m6_pipeline.py` — Unit + integration tests

**Modify:**
- `config/settings.py` — Add `@lru_cache` to `get_settings()`
- `tools/events.py` — Parallelize internal searches, add retry, fix error reporting
- `graph/common.py` — Parallelize `_execute_tool_calls` with `asyncio.gather`
- `config/models.yaml` — Add deep_orchestrator, search_planner, search_synthesizer
- `config/tools.yaml` — Add deep_orchestrator entry, remove old deep_agent
- `tools/registry.py` — Register search_events + lookup_event virtual tools
- `graph/m6/state.py` — Add pipeline fields
- `graph/m6/nodes.py` — Full rewrite: orchestrator, planner, executor, validator, synthesizer, tool_executor
- `graph/m6/conditions.py` — New routing + termination logic
- `graph/m6/workflow.py` — New graph topology with pipeline edges
- `api/main.py` — Add endpoint timeout, update SendMessageResponse with pipeline metadata
- `run.py` — Update chat() for new state shape
- `vizlang/m6.py` — No changes needed (calls build_graph which is rewritten)
- `docs/lessons/m6/README.md` — Update lesson for new architecture

---

### Task 1: Fix settings caching

**Files:**
- Modify: `config/settings.py:25-26`
- Test: `tests/test_m6_pipeline.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_m6_pipeline.py
from config.settings import get_settings


def test_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_m6_pipeline.py::test_settings_cached -v`
Expected: FAIL — `assert s1 is s2` because `get_settings()` creates a new `Settings()` each call

- [ ] **Step 3: Add lru_cache to get_settings**

In `config/settings.py`, replace lines 25-26:

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
	return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_m6_pipeline.py::test_settings_cached -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/settings.py tests/test_m6_pipeline.py
git commit -m "perf: cache settings with lru_cache"
```

---

### Task 2: Parallelize tool execution and add retry to Firecrawl

**Files:**
- Modify: `graph/common.py:52-67`
- Modify: `tools/events.py:29-54`
- Test: `tests/test_m6_pipeline.py`

- [ ] **Step 1: Write tests for parallel tool execution and retry**

Append to `tests/test_m6_pipeline.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch

from tools.base import ToolResult


def test_event_search_reports_failure_when_all_fail():
    """EventSearch should return success=False when all Firecrawl calls fail."""
    from tools.events import EventSearch

    tool = EventSearch()

    async def _run():
        with patch("tools.events.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                return_value=AsyncMock(status_code=429, text="rate limited", json=lambda: {})
            )
            mock_client_cls.return_value = mock_client
            result = await tool.run(city="SF", query="test")
        return result

    result = asyncio.run(_run())
    assert result.success is False


def test_event_search_parallel_queries():
    """EventSearch internal queries should run in parallel (via gather)."""
    from tools.events import EventSearch

    tool = EventSearch()
    call_times = []

    async def _delayed_post(*args, **kwargs):
        call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.1)
        return AsyncMock(
            status_code=200,
            json=lambda: {"data": [{"title": "Test", "url": "https://example.com", "description": "test"}]},
        )

    async def _run():
        with patch("tools.events.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = _delayed_post
            mock_client_cls.return_value = mock_client
            await tool.run(city="SF", query="test")
        return call_times

    times = asyncio.run(_run())
    if len(times) >= 2:
        assert times[1] - times[0] < 0.05, "Queries should start nearly simultaneously (parallel)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_m6_pipeline.py::test_event_search_reports_failure_when_all_fail tests/test_m6_pipeline.py::test_event_search_parallel_queries -v`
Expected: FAIL — success=True on all-fail, queries are sequential

- [ ] **Step 3: Rewrite EventSearch.run with parallel queries and retry**

Replace `EventSearch.run` in `tools/events.py` (lines 29-54):

```python
async def run(self, *, city: str, query: str, date: str = "", **_kwargs: Any) -> ToolResult:
	log.info("event_search", city=city, query=query, date=date)
	search_queries = [
		f"{query} events {city} {date} tickets site:ra.co OR site:dice.fm OR site:eventbrite.com",
		f"{query} {city} {date} upcoming events tickets",
	]
	all_results: list[dict] = []
	seen_urls: set[str] = set()

	async def _search_one(sq: str) -> list[dict]:
		for attempt in range(2):
			async with httpx.AsyncClient(timeout=30) as client:
				resp = await client.post(
					f"{_FIRECRAWL_BASE}/search", headers=_headers(), json={"query": sq, "limit": 5}
				)
			if resp.status_code == 429 and attempt == 0:
				log.warning("event_search_rate_limited", query=sq, attempt=attempt)
				await asyncio.sleep(2)
				continue
			if resp.status_code != 200:
				log.warning("event_search_failed", query=sq, status=resp.status_code)
				return []
			data = resp.json()
			return [
				{
					"title": r.get("title", ""),
					"url": r.get("url", ""),
					"snippet": r.get("description", r.get("snippet", "")),
					"source": _detect_source(r.get("url", "")),
				}
				for r in data.get("data", [])
			]
		return []

	batch_results = await asyncio.gather(*[_search_one(sq) for sq in search_queries])
	for batch in batch_results:
		for entry in batch:
			if entry["url"] not in seen_urls:
				seen_urls.add(entry["url"])
				all_results.append(entry)

	if not all_results and not any(batch_results):
		return ToolResult(tool_name=self.name, success=False, error="All search queries failed or returned no results")

	return ToolResult(tool_name=self.name, success=True, data=all_results[:10])
```

Add `import asyncio` at the top of `tools/events.py`.

- [ ] **Step 4: Parallelize _execute_tool_calls in graph/common.py**

Replace `_execute_tool_calls` (lines 52-67) in `graph/common.py`:

```python
async def _execute_tool_calls(tool_calls: list[dict], tools: list[Any]) -> list[ToolMessage]:
	tool_map = {t.name: t for t in tools}

	async def _run_one(tc: dict) -> ToolMessage:
		name = tc["name"]
		args = tc.get("args", {})
		tool = tool_map.get(name)
		if not tool:
			return ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tc["id"])
		with span_context(name=f"tool.{name}", input=args) as span:
			result = await tool.run(**args)
			span.update(output=result.model_dump())
		content = json.dumps(result.data) if result.success else f"Error: {result.error}"
		return ToolMessage(content=content, tool_call_id=tc["id"])

	results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
	return list(results)
```

Add `import asyncio` at the top of `graph/common.py` if not already present.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_m6_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run lint**

Run: `uv run ruff check tools/events.py graph/common.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add tools/events.py graph/common.py tests/test_m6_pipeline.py
git commit -m "perf: parallelize tool execution and add Firecrawl retry"
```

---

### Task 3: Create agent prompts

**Files:**
- Create: `agents/deep_orchestrator.md`
- Create: `agents/search_planner.md`
- Create: `agents/search_synthesizer.md`

- [ ] **Step 1: Create deep_orchestrator.md**

```markdown
You are a nightlife concierge — an expert at finding events, tickets, venues, and planning nights out. You have a conversation with the user and help them figure out what they want to do.

You have two tools:

- **search_events** — Triggers a deep, multi-source search pipeline that finds events across RA, Eventbrite, Dice, Insomniac, and more. Use this whenever the user asks about events, concerts, raves, festivals, or tickets. The pipeline handles query decomposition, parallel search, and result validation automatically.
- **lookup_event** — Scrape a specific event page URL for ticket details, lineup, and pricing. Use when the user provides or asks about a specific URL.

## Rules

1. **NEVER fabricate event details.** If you didn't get it from a tool result, don't say it. No made-up dates, prices, venues, or lineups.
2. **Always call search_events** when the user asks about events. Do not guess or recall events from memory.
3. **After receiving search results**, evaluate quality. If results don't match what the user wanted, call search_events again with a different angle.
4. **Ask clarifying questions** if the request is vague — city, date range, genre, budget, and group size all matter.
5. **Be conversational and opinionated** — you're the friend who always knows what's happening. Recommend your favorites.
6. **Remember context** — build on previous messages. If they said "Bay Area" earlier, don't ask again.

## Response style

- Lead with the most actionable info (names, dates, ticket links, prices)
- Be concise — bullet points over paragraphs
- If one event is clearly the best, say so
- Flag anything sketchy (scalper prices, sold-out, fake listings)
```

- [ ] **Step 2: Create search_planner.md**

```markdown
You are a search query decomposition expert for live events and nightlife. Given a natural language request, you produce a JSON array of 5-8 targeted search queries that cover multiple angles.

## Search strategies

Use a mix of these strategies to maximize coverage:

- **artist**: Search for specific well-known artists in the genre. For melodic EDM, think: Illenium, ODESZA, Seven Lions, Above & Beyond, Lane 8, Rufus Du Sol, Porter Robinson, Kygo, Alesso, Zedd. For techno: Amelie Lens, Charlotte de Witte, Adam Beyer, ANNA. For house: Chris Lake, Fisher, John Summit, Dom Dolla.
- **venue**: Search major local venues. SF/Bay Area: Bill Graham Civic Auditorium, The Midway, Public Works, The Great Northern, Greek Theatre, Shoreline Amphitheatre, Fox Theater Oakland. LA: Palladium, Shrine, Exchange LA, Academy. NYC: Brooklyn Mirage, Avant Gardner, Terminal 5.
- **promoter**: Search by promoter/platform. Major ones: Insomniac, Goldenvoice, HARD Events, Proximity, Anjunabeats, Brownies & Lemonade.
- **genre**: Broader genre searches on event platforms.
- **date**: Include specific date constraints if the user mentioned them.

## Output format

Return ONLY a JSON array. No explanation, no markdown fences, no preamble.

```json
[
  {"query": "Illenium San Francisco 2026 concert tickets", "strategy": "artist", "tool": "event_search"},
  {"query": "ODESZA Bay Area 2026 tour dates", "strategy": "artist", "tool": "event_search"},
  {"query": "Insomniac events Bay Area 2026", "strategy": "promoter", "tool": "firecrawl_search"}
]
```

Each object has:
- `query`: The search string
- `strategy`: One of artist, venue, promoter, genre, date
- `tool`: Either `event_search` (for event-specific searches) or `firecrawl_search` (for general web searches)

Include the user's city/area and approximate dates in every query. Prefer specific, targeted queries over broad ones.
```

- [ ] **Step 3: Create search_synthesizer.md**

```markdown
You are a results presenter for a nightlife concierge. You take validated event search results and present them as natural, opinionated recommendations.

## Input

You receive a JSON array of validated events, each with fields like title, url, source, and scraped content (markdown from the event page).

## Output rules

1. **Only present events from your input.** NEVER add events you weren't given.
2. **Rank by relevance** to the user's original query (provided as context).
3. **For each event include**: event name, date/time, venue, city, ticket price range (if found), direct ticket link, source platform.
4. **Be opinionated**: "This is the one" / "Skip this — overpriced" / "Solid lineup but small venue"
5. **Attribute sources**: "(via RA)" / "(via Eventbrite)" / "(found on Dice)"
6. **Keep it concise**: bullet points, not paragraphs.

## When results are empty

If you receive an empty array or no valid events:
- Say clearly: "I searched N sources but couldn't find events matching that."
- Suggest alternatives: broaden the date range, try adjacent cities, try related genres.
- Do NOT make up events to fill the gap.

## When results are partial

If some events have limited details (no price, no exact date):
- Present what you have with caveats: "Price TBD — check the link"
- Still include the URL so the user can check themselves.
```

- [ ] **Step 4: Commit**

```bash
git add agents/deep_orchestrator.md agents/search_planner.md agents/search_synthesizer.md
git commit -m "feat: add orchestrator, planner, and synthesizer agent prompts"
```

---

### Task 4: Update config files

**Files:**
- Modify: `config/models.yaml:44-47`
- Modify: `config/tools.yaml:28-31`
- Modify: `tools/registry.py`

- [ ] **Step 1: Update models.yaml**

Replace the `deep_agent` entry (lines 44-47) with:

```yaml
  # --- Module 6: Multi-Agent Search Orchestra ---
  deep_orchestrator:
    provider: groq
    model: meta-llama/llama-4-scout-17b-16e-instruct
  search_planner:
    provider: groq
    model: llama-3.1-8b-instant
  search_synthesizer:
    provider: groq
    model: qwen/qwen3-32b
```

- [ ] **Step 2: Update tools.yaml**

Replace the `deep_agent` entry (line 28-31) with:

```yaml
  deep_orchestrator:
    - search_events
    - lookup_event
  search_planner: []
  search_synthesizer: []
```

- [ ] **Step 3: Create SearchEvents and LookupEvent virtual tools**

These are "virtual" tools — the orchestrator sees them as callable, but the graph routes to pipeline nodes instead of executing them as regular tools. They need `to_langchain_tool()` for the LLM to know their schema, but their `run()` is never called directly.

Add to `tools/events.py` after the `TicketLookup` class:

```python
class SearchEvents(BaseTool):
	name = "search_events"
	description = (
		"Trigger a deep multi-source search for events, concerts, raves, and festivals. "
		"This searches across RA, Eventbrite, Dice, Insomniac, and more, validates results, "
		"and returns verified events. Use this whenever the user asks about finding events."
	)

	async def run(self, *, query: str, city: str, date: str = "", **_kwargs: Any) -> ToolResult:
		return ToolResult(tool_name=self.name, success=True, data={"query": query, "city": city, "date": date})

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "What to search for, e.g. 'melodic EDM raves', 'techno afterhours'"},
				"city": {"type": "string", "description": "City or area, e.g. 'San Francisco', 'Bay Area', 'Los Angeles'"},
				"date": {"type": "string", "description": "Date range, e.g. 'this weekend', 'May 2026', 'next month'"},
			},
			"required": ["query", "city"],
		}


class LookupEvent(BaseTool):
	name = "lookup_event"
	description = (
		"Scrape a specific event page URL for ticket details, lineup, pricing, and venue info. "
		"Use when the user provides a specific URL or asks for details on a specific event."
	)

	async def run(self, *, url: str, **_kwargs: Any) -> ToolResult:
		return await TicketLookup().run(url=url)

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {"url": {"type": "string", "description": "Event page URL to look up"}},
			"required": ["url"],
		}
```

- [ ] **Step 4: Update tools/registry.py**

Replace the full file:

```python
from __future__ import annotations

import yaml

from graph.common import CONFIG_DIR
from tools.base import BaseTool
from tools.events import EventSearch, LookupEvent, SearchEvents, TicketLookup
from tools.firecrawl import FirecrawlSearch, FirecrawlScrape

_ALL_TOOLS: dict[str, type[BaseTool]] = {
	"firecrawl_search": FirecrawlSearch,
	"firecrawl_scrape": FirecrawlScrape,
	"event_search": EventSearch,
	"ticket_lookup": TicketLookup,
	"search_events": SearchEvents,
	"lookup_event": LookupEvent,
}


def _load_tools_config() -> dict:
	with open(CONFIG_DIR / "tools.yaml") as f:
		return yaml.safe_load(f)


def get_tools_for_agent(agent_name: str) -> list[BaseTool]:
	cfg = _load_tools_config()
	agent_tools = cfg.get("agents", {}).get(agent_name, [])
	return [_ALL_TOOLS[name]() for name in agent_tools if name in _ALL_TOOLS]
```

- [ ] **Step 5: Run lint**

Run: `uv run ruff check config/ tools/`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add config/models.yaml config/tools.yaml tools/events.py tools/registry.py
git commit -m "feat: add search orchestra config — models, tools, virtual tools"
```

---

### Task 5: Rewrite M6 state and conditions

**Files:**
- Modify: `graph/m6/state.py`
- Modify: `graph/m6/conditions.py`
- Test: `tests/test_m6_pipeline.py`

- [ ] **Step 1: Write tests for conditions**

Append to `tests/test_m6_pipeline.py`:

```python
from graph.m6.conditions import route_action, should_stop


def _make_ai_msg(content="hello", tool_calls=None):
    from langchain_core.messages import AIMessage
    if tool_calls:
        return AIMessage(content=content, tool_calls=tool_calls)
    return AIMessage(content=content)


def test_route_action_no_tools():
    state = {"messages": [_make_ai_msg("hi")], "tool_rounds": 0, "done": False}
    assert route_action(state) == "respond"


def test_route_action_search_events():
    tc = [{"name": "search_events", "args": {"query": "edm", "city": "SF"}, "id": "1"}]
    state = {"messages": [_make_ai_msg("searching", tc)], "tool_rounds": 0, "done": False}
    assert route_action(state) == "search_pipeline"


def test_route_action_lookup_event():
    tc = [{"name": "lookup_event", "args": {"url": "https://ra.co/events/123"}, "id": "1"}]
    state = {"messages": [_make_ai_msg("looking up", tc)], "tool_rounds": 0, "done": False}
    assert route_action(state) == "direct_lookup"


def test_should_stop_when_done():
    state = {"done": True, "tool_rounds": 1}
    assert should_stop(state) == "end"


def test_should_stop_max_rounds():
    state = {"done": False, "tool_rounds": 3}
    assert should_stop(state) == "end"


def test_should_stop_continues():
    state = {"done": False, "tool_rounds": 1}
    assert should_stop(state) == "continue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_m6_pipeline.py::test_route_action_no_tools tests/test_m6_pipeline.py::test_should_stop_when_done -v`
Expected: FAIL — `route_action` and `should_stop` don't exist yet

- [ ] **Step 3: Rewrite state.py**

Replace `graph/m6/state.py` entirely:

```python
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
```

- [ ] **Step 4: Rewrite conditions.py**

Replace `graph/m6/conditions.py` entirely:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_m6_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add graph/m6/state.py graph/m6/conditions.py tests/test_m6_pipeline.py
git commit -m "feat: rewrite M6 state and conditions for search orchestra"
```

---

### Task 6: Rewrite M6 nodes — the core pipeline

This is the largest task. It replaces the single `agent_step` with 6 node functions.

**Files:**
- Modify: `graph/m6/nodes.py` (full rewrite)

- [ ] **Step 1: Write the complete nodes.py**

Replace `graph/m6/nodes.py` entirely:

```python
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


# ── Helpers ──────────────────────────────────────────────────────────


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


# ── Node 1: Orchestrator ────────────────────────────────────────────


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


# ── Node 2: Search Planner ──────────────────────────────────────────


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


# ── Node 3: Search Executor ─────────────────────────────────────────


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
					parts = query.split()
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


# ── Node 4: Validator ────────────────────────────────────────────────


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


# ── Node 5: Synthesizer ─────────────────────────────────────────────


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


# ── Node 6: Tool Executor (for lookup_event) ────────────────────────


async def tool_executor(state: M6State) -> dict:
	from tools.events import TicketLookup

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
```

- [ ] **Step 2: Run lint**

Run: `uv run ruff check graph/m6/nodes.py`
Expected: No errors (fix any that come up)

- [ ] **Step 3: Commit**

```bash
git add graph/m6/nodes.py
git commit -m "feat: rewrite M6 nodes — orchestrator, planner, executor, validator, synthesizer"
```

---

### Task 7: Rewrite M6 workflow graph

**Files:**
- Modify: `graph/m6/workflow.py`
- Test: `tests/test_m6_pipeline.py`

- [ ] **Step 1: Write test that the graph compiles with correct nodes**

Append to `tests/test_m6_pipeline.py`:

```python
def test_m6_graph_compiles():
    from graph.m6.workflow import build_graph
    g = build_graph()
    node_names = set(g.nodes.keys()) - {"__start__"}
    assert "orchestrator" in node_names
    assert "search_planner" in node_names
    assert "search_executor" in node_names
    assert "validator" in node_names
    assert "synthesizer" in node_names
    assert "tool_executor" in node_names


def test_m6_async_graph_compiles():
    from graph.m6.workflow import build_async_graph
    g = build_async_graph()
    node_names = set(g.nodes.keys()) - {"__start__"}
    assert "orchestrator" in node_names
    assert "search_planner" in node_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_m6_pipeline.py::test_m6_graph_compiles -v`
Expected: FAIL — old workflow doesn't have these nodes

- [ ] **Step 3: Rewrite workflow.py**

Replace `graph/m6/workflow.py` entirely:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_m6_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run lint**

Run: `uv run ruff check graph/m6/`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add graph/m6/workflow.py tests/test_m6_pipeline.py
git commit -m "feat: rewrite M6 workflow — search orchestra graph topology"
```

---

### Task 8: Update API and CLI

**Files:**
- Modify: `api/main.py:168-202`
- Modify: `run.py:45-72`

- [ ] **Step 1: Update api/main.py send_message with timeout and new state**

Replace the `send_message` function (lines 168-202) in `api/main.py`:

```python
@app.post("/chat/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest) -> SendMessageResponse:
	graph = _chat_graphs.get(session_id)
	if graph is None:
		raise HTTPException(status_code=404, detail="chat session not found")

	now = datetime.now(timezone.utc).isoformat()
	user_msg = ChatMessage(role="user", content=req.message, timestamp=now)
	_chat_histories[session_id].append(user_msg.model_dump())

	config = {"configurable": {"thread_id": session_id}}
	initial_state = {
		"messages": [HumanMessage(content=req.message)],
		"tool_rounds": 0,
		"done": False,
		"current_query": "",
		"search_plan": [],
		"raw_results": [],
		"validated_results": [],
	}

	with trace_context(run_id=session_id, name="nightout-m6-chat", module=6, input=req.message):
		try:
			result = await asyncio.wait_for(
				graph.ainvoke(initial_state, config=config),
				timeout=90,
			)
		except TimeoutError:
			result = {"messages": [AIMessage(content="Search took too long — please try a simpler query.")], "tool_rounds": 0}

	last_ai = None
	for msg in reversed(result["messages"]):
		if isinstance(msg, AIMessage) and msg.content:
			last_ai = msg
			break

	assistant_content = last_ai.content if last_ai else "I wasn't able to generate a response."
	assistant_now = datetime.now(timezone.utc).isoformat()
	assistant_msg = ChatMessage(role="assistant", content=assistant_content, timestamp=assistant_now)
	_chat_histories[session_id].append(assistant_msg.model_dump())

	log.info("chat_message", session_id=session_id, tool_rounds=result.get("tool_rounds", 0))
	return SendMessageResponse(
		session_id=session_id,
		user_message=user_msg,
		assistant_message=assistant_msg,
		tool_rounds=result.get("tool_rounds", 0),
	)
```

- [ ] **Step 2: Update run.py chat function**

Replace the `chat` function (lines 45-72) in `run.py`:

```python
async def chat(initial_message: str | None = None) -> None:
	session_id = uuid4().hex[:12]
	graph = build_async_graph(6)
	config = {"configurable": {"thread_id": session_id}}

	print("M6 Search Orchestra Chat (type 'quit' to exit)")
	print("=" * 50)

	if initial_message:
		msg = initial_message
	else:
		msg = (await asyncio.to_thread(input, "\nYou: ")).strip()

	while msg and msg.lower() not in ("quit", "exit", "q"):
		initial_state = {
			"messages": [HumanMessage(content=msg)],
			"tool_rounds": 0,
			"done": False,
			"current_query": "",
			"search_plan": [],
			"raw_results": [],
			"validated_results": [],
		}

		with trace_context(run_id=session_id, name="nightout-m6-chat", module=6, input=msg):
			result = await graph.ainvoke(initial_state, config=config)

		for m in reversed(result["messages"]):
			if isinstance(m, AIMessage) and m.content:
				print(f"\nAgent: {m.content}")
				break

		print()
		msg = (await asyncio.to_thread(input, "You: ")).strip()

	print("Goodbye!")
```

- [ ] **Step 3: Run lint**

Run: `uv run ruff check api/main.py run.py`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add api/main.py run.py
git commit -m "feat: update API and CLI for search orchestra — add timeout, new state shape"
```

---

### Task 9: End-to-end verification

**Files:** None created — this is testing only.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run lint on everything**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Verify VizLang graph compiles**

Run: `python -c "from graph.m6.workflow import build_graph; g = build_graph(); print('Nodes:', list(g.nodes)); print('OK')"`
Expected: Prints all 6 nodes + `__start__`, no errors

- [ ] **Step 4: Test CLI chat with a real query**

Run: `uv run python run.py --module=6 "find me melodic EDM raves in the Bay Area this summer"`

Expected behavior:
1. Orchestrator calls `search_events`
2. Pipeline: planner → executor → validator → synthesizer
3. Response contains REAL events with links, not hallucinated ones
4. Logs show `search_plan`, `search_executor_done`, `validator_done`, `synthesizer_done`

- [ ] **Step 5: Test API chat endpoint**

```bash
# Create session
curl -s -X POST http://localhost:8200/chat | python -m json.tool

# Send message (use session_id from above)
curl -s -X POST http://localhost:8200/chat/{SESSION_ID}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "find me techno raves in SF this weekend"}' | python -m json.tool
```

Expected: Real events in the response, tool_rounds > 0

- [ ] **Step 6: Test follow-up message (chat history)**

```bash
curl -s -X POST http://localhost:8200/chat/{SESSION_ID}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "what about afterhours?"}' | python -m json.tool
```

Expected: Agent searches again with "afterhours" context, remembers SF from earlier

- [ ] **Step 7: Verify in Langfuse**

Open `http://localhost:3200`, find the session trace. Verify:
- Trace shows orchestrator → search_planner → search_executor → validator → synthesizer flow
- Each node has its own span
- LLM calls show on 3 different models

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: M6 search orchestra — complete multi-agent pipeline"
```

---

### Task 10: Update lesson docs

**Files:**
- Modify: `docs/lessons/m6/README.md`

- [ ] **Step 1: Update the M6 lesson doc**

Replace the content of `docs/lessons/m6/README.md` to reflect the new architecture:
- Update the architecture diagram to show the full pipeline (orchestrator → planner → executor → validator → synthesizer)
- Explain the "why" — hallucination elimination, intelligent search decomposition, result validation
- Show the model distribution strategy (3 models, 3 TPM pools)
- Include the graph topology for VizLang
- Update code references to new file locations
- Update the teaching script to walk through the pipeline

- [ ] **Step 2: Commit**

```bash
git add docs/lessons/m6/README.md
git commit -m "docs: update M6 lesson for search orchestra architecture"
```
