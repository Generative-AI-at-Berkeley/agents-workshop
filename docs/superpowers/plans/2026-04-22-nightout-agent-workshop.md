# Night Out Agent — Workshop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-agent nightlife planner that progressively demonstrates 6 architecture patterns — from single LLM call to parallel subagents with octopus merge — as a hands-on workshop for mixed-skill Berkeley AI students.

**Architecture:** LangGraph directed graph with ChatGroq (llama-3.3-70b for manager/merge, llama-3.1-8b for scouts). Firecrawl for real search/scrape tools. Langfuse for observability. FastAPI + React (Tailwind, shadcn-style) frontend. VizLang for visual graph debugging. Each module builds on the last in one linear codebase.

**Tech Stack:** Python 3.13, LangGraph, langchain-groq, Langfuse, Firecrawl, FastAPI, React 19, Tailwind v4, Vite, VizLang

---

## What's Already Built (Module 1 + Infrastructure)

### Infrastructure (DONE)
- Docker Compose with full Langfuse v3 stack (ports: API 8200, Langfuse 3200, PG 5435, CH 8125/9005, Redis 6381, Minio 9200/9201)
- `mise.toml` tasks: `dev`, `down`, `logs`, `api`, `lint`, `format`, `test`, `plan`, `ui`, `ui-install`
- `pyproject.toml` with ruff (120 cols, tabs), ty, pytest-asyncio
- `observability.py` — Langfuse client singleton, `generation_context()`, `span_context()`
- `config/settings.py` — pydantic-settings with `GROQ_API_KEY` + Langfuse keys
- `vizlang_graph.py` — top-level file for VizLang visual debugging

### Module 1: Single Agent + Observability (DONE)
- `schemas/nightout.py` — `NightOutRequest`, `Stop`, `Itinerary` (Pydantic v2)
- `agents/planner.md` — nightlife planner system prompt
- `config/models.yaml` — `planner: llama-3.3-70b-versatile`
- `graph/state.py` — `NightOutState` TypedDict (request, messages, plan, raw_research, itinerary, review_passed, review_feedback, attempts)
- `graph/nodes.py` — `plan_night()` node: loads prompt + model from config, calls Groq, parses JSON → `Itinerary`
- `graph/workflow.py` — single-node graph: `START → plan_night → END`
- `api/main.py` — FastAPI with `POST /runs` (async execution) and `GET /runs/{id}`
- `run.py` — CLI entrypoint
- Full React UI: home page (city/vibe/date/group_size form), run page (timeline with stop cards, degen scores, survival tips), shadcn-style components (Card, Button, Input, Badge, Spinner), dark mode, Inter font

### Existing Agent Prompts
- `agents/planner.md` — high-level night planner (used in Module 1, becomes the "plan" node in Module 2)
- `agents/scout.md` — venue researcher (written but not yet wired into any node)

---

## Decisions Log

| Decision | Alternatives Considered | Why |
|----------|------------------------|-----|
| Groq as sole LLM provider | Anthropic, OpenAI, multi-provider | Free tier, fast inference, simple (one API key for attendees) |
| 70b for manager/merge, 8b for scouts | Single model for all | Teaches cost/latency tradeoffs per agent role |
| Firecrawl as sole tool | Tavily, SerpAPI, multi-tool | 20k free student credits, one API key |
| Progressive abstraction (code-first → config-driven) | Config-driven from start | Each abstraction arrives when the previous module's approach hits a wall |
| JSON output to `output/` | FastAPI streaming, WebSocket | Workshop simplicity — Langfuse traces are the visual layer |
| Electric purple brand color | Neon green (degen), blue | Nightlife theme, distinct from degen |
| VizLang for graph debugging | Print statements, Langfuse only | Visual canvas matches workshop teaching goals perfectly |

---

## Module 2: Directed Graph with Conditional Edges + Checkpointing

**Teaching point:** "90% of production agents are directed graphs, not autonomous loops. The graph IS the product spec."

**Graph shape:**
```
START → plan → scout → synthesize → review →(pass)→ END
                                       ↓(fail, attempts < 3)
                                     scout
                                       ↓(fail, attempts >= 3)
                                      END
```

### Task 2.1: Add New Agent Prompts

**Files:**
- Modify: `agents/planner.md` (simplify — it now only creates a rough plan, not the final itinerary)
- Keep: `agents/scout.md` (already written)
- Create: `agents/synthesizer.md`
- Create: `agents/reviewer.md`
- Modify: `config/models.yaml` (add scout, synthesizer, reviewer entries)

- [ ] **Step 1: Update planner prompt to output a rough plan, not a full itinerary**

Replace `agents/planner.md` with a version that outputs a text plan (list of stop ideas with categories and rough times) instead of structured JSON. The planner is now the "idea guy" — the synthesizer handles the structured output.

```markdown
You are a legendary nightlife planner. You know every city's underground scene.

Given a city, vibe, date, and group size, create a ROUGH PLAN for the night — a list of stops with categories, rough times, and why each stop fits the vibe.

Rules:
- Start with a pregame (dinner, bar, rooftop)
- Build energy — don't peak too early
- Include at least one club or rave as the main event
- End with a recovery food spot
- Be specific with venue names — no "find a club" nonsense
- Include 5-7 stops total

Output format — plain text, one stop per line:
[TIME] [CATEGORY] - [VENUE NAME]: [why this fits the vibe]

Example:
20:00 pregame - Klunkerkranich: rooftop bar with sunset views, good warm-up energy
23:00 club - Watergate: techno on the river, solid lineup this weekend

You're not a travel agent. You're the friend who always knows where to go.
```

- [ ] **Step 2: Create synthesizer prompt**

Create `agents/synthesizer.md`:

```markdown
You are a nightlife itinerary synthesizer. Given a rough plan and detailed venue research, produce a polished structured itinerary.

Your job:
- Merge the plan's stop order with the research's details
- Resolve contradictions (if research says a venue is closed, drop it and note why)
- Fill in missing details (addresses, costs, tips) from the research
- Assign a degen_score to each stop (1=tame, 10=absolutely unhinged)
- Calculate total estimated cost per person
- Write survival tips for the group

Respond with a JSON object:
- city, date, vibe, group_size: echo from the plan context
- stops: array of {time, name, category, vibe, address, cost, tips, degen_score}
- total_estimated_cost: string
- survival_tips: string

JSON only, no markdown fences.
```

- [ ] **Step 3: Create reviewer prompt**

Create `agents/reviewer.md`:

```markdown
You are a brutally honest nightlife reviewer. Given an itinerary, review it for quality.

Check:
- Does the energy flow make sense? (Don't go from chill bar to hardcore rave with nothing in between)
- Are the times realistic? (No 30-minute gaps between venues across the city)
- Is there variety? (Not 4 clubs in a row)
- Is the recovery meal included?
- Are the degen_scores consistent? (A jazz bar shouldn't be 8/10)
- Does it actually match the requested vibe?

If the itinerary is GOOD, respond with exactly:
APPROVED

If it needs work, respond with:
NEEDS_REVISION: [specific feedback on what to fix]

Be specific. "Add more variety" is useless. "Replace the second techno club with a dive bar to break up the energy" is useful.
```

- [ ] **Step 4: Update models.yaml**

```yaml
agents:
  planner:
    provider: groq
    model: llama-3.3-70b-versatile
  scout:
    provider: groq
    model: llama-3.1-8b-instant
  synthesizer:
    provider: groq
    model: llama-3.3-70b-versatile
  reviewer:
    provider: groq
    model: llama-3.1-8b-instant
```

- [ ] **Step 5: Commit**

```bash
git add agents/ config/models.yaml
git commit -m "feat(module-2): add scout, synthesizer, reviewer agent prompts + model config"
```

### Task 2.2: Implement Multi-Node Graph

**Files:**
- Modify: `graph/nodes.py` (replace single `plan_night` with `plan`, `scout`, `synthesize`, `review`)
- Create: `graph/conditions.py` (review pass/fail routing)
- Modify: `graph/workflow.py` (wire up the 4-node graph with conditional edge)
- Modify: `graph/__init__.py` (update export)
- Modify: `vizlang_graph.py` (still just re-exports — no change needed)

- [ ] **Step 1: Rewrite `graph/nodes.py` with all four nodes**

Each node follows the same pattern: load prompt from `agents/*.md`, load model from `config/models.yaml`, call Groq, update state. The key difference is what each node reads from and writes to in the state.

```python
from __future__ import annotations

import json
from pathlib import Path

import structlog
import yaml
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

from config.settings import get_settings
from graph.state import NightOutState
from observability import generation_context
from schemas.nightout import Itinerary

log = structlog.get_logger(__name__)

AGENTS_DIR = Path("agents")
CONFIG_DIR = Path("config")


def _load_agent_prompt(agent_name: str) -> str:
	return (AGENTS_DIR / f"{agent_name}.md").read_text()


def _load_model_config(agent_name: str) -> dict:
	with open(CONFIG_DIR / "models.yaml") as f:
		cfg = yaml.safe_load(f)
	return cfg["agents"][agent_name]


def _build_llm(agent_name: str) -> ChatGroq:
	model_cfg = _load_model_config(agent_name)
	settings = get_settings()
	return ChatGroq(
		model=model_cfg["model"],
		api_key=settings.GROQ_API_KEY,
		temperature=0.7,
	)


async def _call_agent(agent_name: str, user_msg: str) -> str:
	system_prompt = _load_agent_prompt(agent_name)
	model_cfg = _load_model_config(agent_name)
	llm = _build_llm(agent_name)
	messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

	with generation_context(name=f"agent.{agent_name}", model=model_cfg["model"], input=user_msg) as gen:
		response = await llm.ainvoke(messages)
		gen.update(output=response.content)

	log.info("agent_complete", agent=agent_name, response_length=len(response.content))
	return response.content


async def plan(state: NightOutState) -> dict:
	"""Create a rough plan — list of stop ideas."""
	request = state["request"]
	feedback = state.get("review_feedback", "")

	user_msg = (
		f"City: {request.city}\n"
		f"Vibe: {request.vibe}\n"
		f"Date: {request.date}\n"
		f"Group size: {request.group_size}\n"
	)
	if request.notes:
		user_msg += f"Notes: {request.notes}\n"
	if feedback:
		user_msg += f"\nPrevious attempt was rejected. Feedback: {feedback}\nAdjust your plan accordingly.\n"

	result = await _call_agent("planner", user_msg)
	return {"plan": result}


async def scout(state: NightOutState) -> dict:
	"""Research each venue in the plan with real details."""
	plan_text = state["plan"]
	request = state["request"]

	user_msg = (
		f"Research the following night out plan for {request.city}:\n\n"
		f"{plan_text}\n\n"
		f"Provide detailed info for each stop."
	)

	result = await _call_agent("scout", user_msg)
	return {"raw_research": result}


async def synthesize(state: NightOutState) -> dict:
	"""Merge plan + research into a structured Itinerary."""
	request = state["request"]

	user_msg = (
		f"City: {request.city}\nDate: {request.date}\n"
		f"Vibe: {request.vibe}\nGroup size: {request.group_size}\n\n"
		f"ROUGH PLAN:\n{state['plan']}\n\n"
		f"VENUE RESEARCH:\n{state['raw_research']}\n\n"
		f"Produce the final JSON itinerary."
	)

	result = await _call_agent("synthesizer", user_msg)
	itinerary = Itinerary.model_validate_json(result)
	return {"itinerary": itinerary}


async def review(state: NightOutState) -> dict:
	"""Review the itinerary — approve or request revision."""
	itinerary = state["itinerary"]
	attempts = state.get("attempts", 0) + 1

	user_msg = f"Review this itinerary:\n\n{json.dumps(itinerary.model_dump(), indent=2)}"

	result = await _call_agent("reviewer", user_msg)
	passed = result.strip().startswith("APPROVED")
	feedback = "" if passed else result.replace("NEEDS_REVISION:", "").strip()

	log.info("review_complete", passed=passed, attempts=attempts)
	return {
		"review_passed": passed,
		"review_feedback": feedback,
		"attempts": attempts,
	}
```

- [ ] **Step 2: Create `graph/conditions.py`**

```python
from graph.state import NightOutState

MAX_ATTEMPTS = 3


def should_retry(state: NightOutState) -> str:
	if state.get("review_passed", False):
		return "end"
	if state.get("attempts", 0) >= MAX_ATTEMPTS:
		return "end"
	return "retry"
```

- [ ] **Step 3: Rewrite `graph/workflow.py`**

```python
from langgraph.graph import StateGraph, START, END

from graph.conditions import should_retry
from graph.nodes import plan, scout, synthesize, review
from graph.state import NightOutState


def build_graph() -> StateGraph:
	builder = StateGraph(NightOutState)

	builder.add_node("plan", plan)
	builder.add_node("scout", scout)
	builder.add_node("synthesize", synthesize)
	builder.add_node("review", review)

	builder.add_edge(START, "plan")
	builder.add_edge("plan", "scout")
	builder.add_edge("scout", "synthesize")
	builder.add_edge("synthesize", "review")

	builder.add_conditional_edges("review", should_retry, {
		"end": END,
		"retry": "plan",
	})

	return builder.compile()


# Module-level compiled graph for VizLang
graph = build_graph()
```

- [ ] **Step 4: Update `api/main.py` to pass full initial state**

Update the `_execute_run` function's `graph.ainvoke()` call to include all state fields:

```python
result = await graph.ainvoke({
	"request": request,
	"messages": [],
	"plan": "",
	"raw_research": "",
	"itinerary": None,
	"review_passed": False,
	"review_feedback": "",
	"attempts": 0,
})
```

- [ ] **Step 5: Update `run.py` similarly**

Update the `graph.ainvoke()` call in `run.py` to pass the full initial state (same fields as above).

- [ ] **Step 6: Test via CLI**

```bash
uv run python run.py "berlin" "techno, underground" "this saturday" 4
```

Expected: see 4 log lines (`agent_complete` for planner, scout, synthesizer, reviewer), then JSON output. If review rejects, see a second loop (planner → scout → synthesize → review again).

- [ ] **Step 7: Test in VizLang**

Open `vizlang_graph.py` in VizLang. Should now show 4 nodes with the conditional edge from `review` back to `plan`. Click Run with the same JSON input. Watch nodes light up sequentially.

- [ ] **Step 8: Commit**

```bash
git add graph/ api/main.py run.py
git commit -m "feat(module-2): directed graph with plan→scout→synthesize→review + conditional retry"
```

---

## Module 3: Tools (Firecrawl) + RBAC

**Teaching point:** "Without RBAC, every agent can do everything — unpredictable behavior + security holes. Config-driven tool permissions."

### Task 3.1: Implement Firecrawl Tool Layer

**Files:**
- Create: `tools/base.py` (abstract tool interface)
- Create: `tools/firecrawl.py` (search + scrape wrappers)
- Create: `tools/registry.py` (RBAC: which agents can use which tools)
- Modify: `config/tools.yaml` (define tool→agent permissions)
- Modify: `config/settings.py` (add `FIRECRAWL_API_KEY`)
- Modify: `.env.example` (add `FIRECRAWL_API_KEY`)
- Modify: `pyproject.toml` (add `firecrawl-py` dependency)

- [ ] **Step 1: Add firecrawl dependency**

Add `'firecrawl-py'` to `pyproject.toml` dependencies. Run `uv sync`.

- [ ] **Step 2: Add `FIRECRAWL_API_KEY` to settings + `.env.example`**

Add `FIRECRAWL_API_KEY: str | None = None` to `config/settings.py` Settings class. Add `FIRECRAWL_API_KEY=` to `.env.example`.

- [ ] **Step 3: Create `tools/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pydantic import BaseModel


class ToolResult(BaseModel):
	tool_name: str
	success: bool
	data: str
	error: str = ""


class BaseTool(ABC):
	name: str
	description: str

	@abstractmethod
	async def run(self, **kwargs: str) -> ToolResult: ...
```

- [ ] **Step 4: Create `tools/firecrawl.py`**

Two tools: `firecrawl_search` (search the web) and `firecrawl_scrape` (scrape a URL). Both return `ToolResult`. Use `httpx` (not requests). Handle errors gracefully — return `ToolResult(success=False, error=...)`, never raise.

- [ ] **Step 5: Create `tools/registry.py`**

Reads `config/tools.yaml`. Exposes `get_tools_for_agent(agent_name: str) -> list[BaseTool]`. Only returns tools the agent is allowed to use per the YAML config.

- [ ] **Step 6: Define RBAC in `config/tools.yaml`**

```yaml
tools:
  firecrawl_search:
    agents: [scout]
  firecrawl_scrape:
    agents: [scout]
```

Only the `scout` agent gets search/scrape tools. Planner, synthesizer, and reviewer are pure LLM reasoning — no tools.

- [ ] **Step 7: Wire tools into the scout node**

Modify `graph/nodes.py` `scout()` to: (1) get its tools from the registry, (2) pass tool descriptions to the LLM, (3) handle tool_calls in the response, (4) execute tools and feed results back. Use LangChain's tool-calling pattern with `ChatGroq.bind_tools()`.

- [ ] **Step 8: Test — remove scout's tool permission, verify it degrades gracefully**

Temporarily remove `scout` from `tools.yaml` `firecrawl_search.agents`. Run the agent. Scout should still produce output (just from LLM knowledge, no search). Re-add the permission.

- [ ] **Step 9: Commit**

```bash
git add tools/ config/ pyproject.toml .env.example graph/nodes.py
git commit -m "feat(module-3): firecrawl tools + config-driven RBAC"
```

---

## Module 4: Subagents

**Teaching point:** "The manager doesn't do the work — it delegates. Trace shows parent→child spans."

### Task 4.1: Create Specialized Scout Subagents

**Files:**
- Create: `agents/club_scout.md`
- Create: `agents/rave_scout.md`
- Create: `agents/food_scout.md`
- Create: `agents/afterhours_scout.md`
- Create: `agents/ticket_scout.md`
- Create: `agents/manager.md`
- Modify: `config/models.yaml` (add all scout + manager entries, scouts use 8b, manager uses 70b)
- Modify: `config/tools.yaml` (give each scout appropriate tool permissions)
- Modify: `graph/nodes.py` (replace single `scout` with `manage_scouts` that spawns subagents)
- Modify: `graph/workflow.py` (update graph wiring)

- [ ] **Step 1: Create subagent prompts**

Each scout gets a focused prompt:
- `club_scout.md` — finds clubs matching the vibe, checks lineups, door policies
- `rave_scout.md` — finds warehouse raves, underground events, afterparties
- `food_scout.md` — finds late-night/early-morning food spots, recovery meals
- `afterhours_scout.md` — finds afterhours venues, sunrise spots
- `ticket_scout.md` — finds ticket links, pre-sale info, guest list options
- `manager.md` — decides which scouts to dispatch based on the plan, collects results

- [ ] **Step 2: Update `config/models.yaml`**

```yaml
agents:
  planner:
    provider: groq
    model: llama-3.3-70b-versatile
  manager:
    provider: groq
    model: llama-3.3-70b-versatile
  club_scout:
    provider: groq
    model: llama-3.1-8b-instant
  rave_scout:
    provider: groq
    model: llama-3.1-8b-instant
  food_scout:
    provider: groq
    model: llama-3.1-8b-instant
  afterhours_scout:
    provider: groq
    model: llama-3.1-8b-instant
  ticket_scout:
    provider: groq
    model: llama-3.1-8b-instant
  synthesizer:
    provider: groq
    model: llama-3.3-70b-versatile
  reviewer:
    provider: groq
    model: llama-3.1-8b-instant
```

- [ ] **Step 3: Update `config/tools.yaml` with per-scout RBAC**

```yaml
tools:
  firecrawl_search:
    agents: [club_scout, rave_scout, food_scout, afterhours_scout, ticket_scout]
  firecrawl_scrape:
    agents: [club_scout, rave_scout, food_scout, afterhours_scout, ticket_scout]
```

Manager gets NO tools — it only orchestrates. Synthesizer and reviewer get NO tools — pure reasoning.

- [ ] **Step 4: Implement `manage_scouts` node**

Replace the `scout` node in `graph/nodes.py` with a `manage_scouts` function that:
1. Reads the plan to decide which scouts to dispatch
2. Calls each scout sequentially (parallel comes in Module 5)
3. Collects all results into `raw_research`
4. Uses `span_context()` for each subagent call so Langfuse shows nested spans

- [ ] **Step 5: Update graph wiring**

`START → plan → manage_scouts → synthesize → review → conditional`

- [ ] **Step 6: Test and verify Langfuse traces show parent→child spans**

Run via CLI. Check Langfuse at `http://localhost:3200` — the trace should show `manage_scouts` as a parent span with individual scout spans nested inside.

- [ ] **Step 7: Commit**

```bash
git add agents/ config/ graph/
git commit -m "feat(module-4): subagents — manager dispatches specialized scouts"
```

---

## Module 5: Parallel Fan-Out + Octopus Merge

**Teaching point:** "Fan-out is easy. Merge is the product. Wall-clock time drops dramatically."

### Task 5.1: Parallelize Scout Dispatch

**Files:**
- Modify: `graph/nodes.py` (use `asyncio.gather` for parallel scout calls)
- Create: `agents/merge.md` (octopus merge prompt)
- Modify: `graph/nodes.py` (add `merge` node)
- Modify: `graph/workflow.py` (fan-out/fan-in edges, or keep using the `manage_scouts` node with internal parallelism)
- Modify: `config/models.yaml` (add merge agent)

- [ ] **Step 1: Make scouts run in parallel**

In `manage_scouts`, change from sequential calls to `asyncio.gather(*scout_tasks)`. Each task is a call to `_call_agent(scout_name, msg)` wrapped with tool execution.

- [ ] **Step 2: Create merge prompt**

Create `agents/merge.md` — takes N scout results, deduplicates venues, resolves contradictions (e.g., two scouts recommend the same club at different times), and produces a unified research report.

- [ ] **Step 3: Add merge node**

After parallel scouts complete, a `merge` node takes the raw results and produces a single coherent `raw_research` string. This replaces the simple concatenation from Module 4.

- [ ] **Step 4: Update graph**

`START → plan → manage_scouts (parallel internally) → merge → synthesize → review → conditional`

- [ ] **Step 5: Add wall-clock timing**

Log elapsed time for the scout phase. Compare Module 4 (sequential) vs Module 5 (parallel) in the workshop demo.

- [ ] **Step 6: Test**

Run via CLI. Verify all scouts complete, merge produces coherent output, and total time is lower than sequential.

- [ ] **Step 7: Commit**

```bash
git add agents/ config/ graph/
git commit -m "feat(module-5): parallel scout fan-out + octopus merge"
```

---

## Module 6: Deep Agent Contrast

**Teaching point:** "Directed vs deep — when to use which. Most production systems are directed. Research/coding assistants are deep."

### Task 6.1: Build Open-Loop Deep Agent

**Files:**
- Create: `agents/deep_planner.md` (single agent with broad instructions + all tools)
- Create: `graph/deep.py` (open-loop ReAct agent using LangGraph's prebuilt `create_react_agent`)
- Modify: `config/models.yaml` (add `deep_planner` entry)
- Modify: `config/tools.yaml` (give `deep_planner` all tools)
- Modify: `run.py` (add `--mode deep` flag)
- Modify: `api/main.py` (add `mode` field to `CreateRunRequest`)

- [ ] **Step 1: Create deep planner prompt**

`agents/deep_planner.md` — a single agent that gets the full nightlife planning task, all tools, and no predefined workflow. It decides what to search, when to stop, and how to structure the output. Same JSON output schema as the directed graph.

- [ ] **Step 2: Create `graph/deep.py`**

Use LangGraph's `create_react_agent` or a simple tool-calling loop:
1. Agent gets the user request + all tools
2. Agent decides what to do (search, scrape, think)
3. Loop until it produces the final itinerary JSON
4. No predefined nodes — the agent IS the control flow

```python
from langgraph.prebuilt import create_react_agent

def build_deep_graph():
    tools = get_all_tools()  # no RBAC — deep agent gets everything
    llm = _build_llm("deep_planner")
    return create_react_agent(llm, tools)
```

- [ ] **Step 3: Add `--mode` flag to CLI and API**

`run.py` accepts `--mode directed` (default) or `--mode deep`. API's `CreateRunRequest` gets an optional `mode` field.

- [ ] **Step 4: Run both modes on the same prompt, compare**

Same input: "berlin, techno, underground, this saturday, 4 people"
- Directed: predictable multi-node flow, ~4 LLM calls, ~5-8 seconds
- Deep: unpredictable tool-calling loop, variable LLM calls, variable time

Compare Langfuse traces side-by-side in the workshop.

- [ ] **Step 5: Commit**

```bash
git add agents/deep_planner.md graph/deep.py run.py api/main.py config/
git commit -m "feat(module-6): deep agent contrast — open-loop ReAct for comparison"
```

---

## Testing Strategy

Each module should be testable after implementation:

| Module | Test command | What to verify |
|--------|-------------|----------------|
| 1 | `uv run python run.py "sf" "techno" "tonight"` | JSON itinerary printed |
| 2 | Same CLI command | 4 agent log lines, possible retry loop |
| 3 | Same + check Firecrawl called | Scout uses search tool, others don't |
| 4 | Same + check Langfuse | Nested spans for each scout |
| 5 | Same + compare timing | Parallel faster than Module 4 |
| 6 | `uv run python run.py --mode deep "sf" "techno"` | Deep agent produces itinerary via tool loop |

VizLang can be used at every module to visually verify the graph shape matches expectations.

---

## UI Updates Per Module

The UI (already built) shows the itinerary timeline. It does NOT need changes per module — the output schema (`Itinerary` with `stops`) stays the same throughout. The graph internals change but the API contract (`POST /runs` → `GET /runs/{id}` → `itinerary`) is stable.

Optional UI enhancements (not blocking):
- Show which module/mode was used in the run header
- Show agent trace timeline (like degen's `RunTimeline`) — can be added if time permits
