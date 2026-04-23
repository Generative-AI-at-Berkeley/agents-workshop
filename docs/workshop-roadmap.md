# Night Out Agent — Workshop Roadmap

**Audience:** Generative AI at Berkeley, mixed-skill, ~4-5 hours
**Concept:** Given a city, vibe, date, and group size → plan a full night out (clubs, raves, afterhours, food)
**Stack:** Python 3.13, LangGraph, ChatGroq (llama-3.3-70b + llama-3.1-8b), Firecrawl, Langfuse, FastAPI, React 19, VizLang

---

## Status

| Module | Status | Teaching Point |
|--------|--------|----------------|
| 1. Single Agent + Observability | **DONE** | "One LLM call is an agent. Observability makes it debuggable." |
| +Bonus: Context Engineering | | "Prompt engineering is dead. Context engineering is the real skill." |
| 2. Directed Graph + Conditional Edges | **DONE** | "90% of production agents are directed graphs. The graph IS the product spec." |
| 3. Tools (Firecrawl) + RBAC | **DONE** | "Without RBAC, every agent can do everything. Config-driven permissions." |
| 4. Subagents | **DONE** | "The manager doesn't do the work — it delegates. Traces show parent→child." |
| 5. Parallel Fan-Out + Octopus Merge | **DONE** | "Fan-out is easy. Merge is the product. Wall-clock time drops dramatically." |
| +Bonus: GraphRAG + Agent Memory | | "Stateless → stateful is the leap from tool to teammate." |
| 6. Deep Agent Contrast | TODO | "Directed vs deep — when to use which." |

---

## Module 1: Single Agent + Observability (DONE)

**Graph:** `START → plan_night → END`

One node, one LLM call. Planner agent gets the request, returns a full JSON itinerary.
- Langfuse traces every generation
- CLI (`run.py`) and API (`POST /runs`, `GET /runs/{id}`) both work
- UI shows timeline with stop cards, degen scores, survival tips

**Key files:** `graph/m1/`, `agents/planner_v1.md`, `schemas/nightout.py`

> **Bonus: Context Engineering** — Prompt engineering is dead. The real skill is curating what goes into the context window, in what order, at what moment. The `.md` system prompts in `agents/` are context engineering — the planner prompt isn't just instructions, it's a carefully ordered context payload: role, constraints, output format, examples. The next level is making prompts evolve based on what worked: if the reviewer keeps rejecting plans for missing afterhours spots, the planner prompt should learn that. Static prompts are v1. Dynamic context assembly is the production skill.

---

## Module 2: Directed Graph + Conditional Edges (DONE)

**Graph:** `START → plan → scout → synthesize → review →(pass)→ END`
`review →(fail, <3 attempts)→ plan` (retry loop)
`review →(fail, ≥3 attempts)→ END` (bail out)

Split the monolith into 4 specialized agents:
- **planner** (70b) — rough plan, text output, "idea guy"
- **scout** (8b) — venue research, flesh out details
- **synthesizer** (70b) — merge plan + research → structured JSON itinerary
- **reviewer** (8b) — approve or reject with specific feedback

Conditional edge from review: if rejected and under 3 attempts, loops back to plan with feedback.

**Key files:** `graph/m2/`, `agents/{planner,scout,synthesizer,reviewer}.md`

---

## Module 3: Tools (Firecrawl) + RBAC (DONE)

**Graph:** Same shape as M2: `START → plan → scout → synthesize → review → conditional`
**What changes:** Scout gets real search/scrape tools via `bind_tools()` + tool-calling loop. Other agents get nothing — enforced by `config/tools.yaml`.

New infrastructure:
- `tools/base.py` — `BaseTool` ABC + `ToolResult` model
- `tools/firecrawl.py` — `FirecrawlSearch` + `FirecrawlScrape` (httpx, async)
- `tools/registry.py` — reads `config/tools.yaml`, returns tools by agent name
- `config/tools.yaml` — RBAC: only `scout` gets `firecrawl_search` + `firecrawl_scrape`
- `graph/common.py` — `call_agent_with_tools()` does `bind_tools()` + up to 5 rounds of tool calls
- Scout prompt updated to instruct tool usage

**RBAC demo:** Remove scout's tools in `tools.yaml` → scout still works (LLM knowledge only, no search). Add them back → scout searches live.

**Key files:** `graph/m3/`, `tools/`, `config/tools.yaml`, `agents/scout.md`

**Teaching moment:** Show the YAML, show what happens when you revoke a tool, show Langfuse tool spans.

---

## Module 4: Subagents (DONE)

**Graph:** `START → plan → manage_scouts → synthesize → review → conditional`
**What changes:** Single `scout` splits into 5 specialized scouts + a manager that delegates.

New agents (all 8b, all with firecrawl tools):
- `club_scout` — clubs, DJ lineups, door policies
- `rave_scout` — warehouse raves, underground events
- `food_scout` — late-night food, recovery meals
- `afterhours_scout` — afterhours venues, sunrise spots
- `ticket_scout` — ticket links, pre-sale, guest lists

New agent (70b, no tools):
- `manager` — reads plan, outputs JSON assignments, scouts execute sequentially

The `manage_scouts` node: manager LLM returns `{"assignments": [...]}`, then each scout is called sequentially with `span_context()` for nested Langfuse traces.

**Key files:** `graph/m4/`, `agents/{manager,club_scout,rave_scout,food_scout,afterhours_scout,ticket_scout}.md`

**Teaching moment:** Show Langfuse trace with manager → N child spans. Sequential is slow — motivates Module 5.

---

## Module 5: Parallel Fan-Out + Octopus Merge (DONE)

**Graph:** `START → plan → manage_scouts (parallel) → merge → synthesize → review → conditional`
**What changes:** Scouts run in parallel (`asyncio.gather`). New merge agent deduplicates.

- Async `amanage_scouts` uses `asyncio.gather(*scout_tasks)` — all scouts fire simultaneously
- Sync VizLang variant still runs sequentially (no async event loop)
- `merge` node (70b) deduplicates and reconciles conflicting scout reports
- Wall-clock time logged for comparison with M4's sequential approach
- New state field: `merged_research` (synthesizer reads this instead of raw)

**Key files:** `graph/m5/`, `agents/merge.md`

**Teaching moment:** Same result, fraction of the time. Show the timing comparison. Merge is where the product logic lives.

> **Bonus: GraphRAG + Agent Memory** — Right now scouts scrape cold every run and forget everything. What if the agent built a living knowledge graph of every venue, DJ, promoter, and afterhours spot it's ever found — nodes connected by relationships like "plays b2b with", "same promoter", "afterhours follows this club" — and got smarter every run? That's GraphRAG + agent memory. Run 1: cold scrape, slow. Run 10: the agent already knows that Monarch feeds into The Great Northern on tech house nights, that El Farolito is the canonical 3am recovery spot, that a specific promoter runs the best warehouse raves in SOMA. Stateless vs stateful is the leap from tool to teammate.

---

## Module 6: Deep Agent Contrast

**What changes:** Build a single open-loop ReAct agent as a contrast to the directed graph.

**Build order:**
1. `agents/deep_planner.md` — one agent, all tools, no predefined workflow
2. `graph/deep.py` — use `create_react_agent` from LangGraph prebuilt
3. Add `--mode deep` flag to CLI and `mode` field to API
4. Run both modes on same prompt, compare Langfuse traces side-by-side

**Teaching moment:** Directed = predictable, fast, auditable. Deep = flexible, unpredictable, expensive. Most production systems should be directed. Research/coding assistants are where deep agents shine.

---

## Decisions

| Decision | Why |
|----------|-----|
| Groq only (free tier) | One API key, fast inference, simple for workshop |
| 70b for manager/merge, 8b for scouts | Teaches cost/latency tradeoffs per role |
| Firecrawl only | 20k free student credits |
| Progressive abstraction | Each module's pain motivates the next abstraction |
| Same output schema throughout | UI stays stable, only graph internals change |
| VizLang at every module | Visual graph = instant understanding |

---

## How to Test Each Module

Each module is self-contained: its own state, nodes, workflow, and VizLang file.

```
# CLI — pick a module with --module N (default: 2)
uv run python run.py --module=1 "san francisco" "techno" "this saturday" 4
uv run python run.py --module=2 "san francisco" "techno" "this saturday" 4

# API — pass "module": N in POST body (default: 2)
curl -X POST localhost:8200/runs -H 'Content-Type: application/json' \
  -d '{"city":"sf","vibe":"techno","date":"tonight","group_size":4,"module":1}'

# VizLang — one file per module
#   vizlang/m1.py → single node (plan_night → END)
#   vizlang/m2.py → 4-node graph with conditional retry
#   Right-click → "Open in VizLang"

# API server
mise run api            # starts on :8200

# UI
mise run ui             # starts on :5174

# Langfuse (needs Docker)
mise run dev            # docker compose up
# UI at http://localhost:3200
```

---

## Architecture

Each module lives in `graph/mN/` with its own state, nodes, and workflow:

```
graph/
  common.py              — shared: call_agent, _build_llm, _load_agent_prompt
  registry.py            — build_graph(module=N) dispatcher + initial_state()
  m1/state.py, nodes.py, workflow.py
  m2/state.py, nodes.py, conditions.py, workflow.py
  m3/ ...                — future modules slot in here

vizlang/
  m1.py                  — VizLang entry for Module 1
  m2.py                  — VizLang entry for Module 2
  latest.py              — VizLang entry for latest module (default)
```

`run.py` and `api/main.py` both use `graph.registry.build_graph(module)` — no hardcoded imports.

---

## What's Already Built

- Docker Compose with full Langfuse v3 stack
- `mise.toml` tasks for everything
- `observability.py` with `generation_context()` + `span_context()`
- `config/settings.py` (pydantic-settings)
- Full React UI (dark mode, purple theme, timeline, stop cards, degen scores)
- `vizlang/` directory with per-module VizLang files
- Module 1 + Module 2 code (isolated, both runnable independently)
