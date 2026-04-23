# M6: Multi-Agent Search Orchestra — Design Spec

## Goal

Replace the current single-agent ReAct deep agent (which hallucinates fake events instead of using tools) with a multi-agent search pipeline that eliminates hallucination by design, searches intelligently across multiple angles, validates results before presenting them, and distributes LLM load across Groq's free-tier models to avoid TPM limits.

## Architecture

```
User Message → Orchestrator (ReAct, llama-4-scout-17b)
                    │
                    ├─ calls search_events(query, city)
                    │     │
                    │     ├─ Search Planner (LLM, llama-3.1-8b-instant)
                    │     │     → 5-8 targeted search queries
                    │     │
                    │     ├─ Search Executor (pure function, no LLM)
                    │     │     → parallel Firecrawl searches via asyncio.gather
                    │     │     → deduplicated raw results
                    │     │
                    │     ├─ Validator (pure function, no LLM)
                    │     │     → parallel ticket_lookup on top results
                    │     │     → filters dead/fake/outdated entries
                    │     │
                    │     └─ Synthesizer (LLM, qwen/qwen3-32b)
                    │           → ranked recommendations with links/prices
                    │           → added to messages as AIMessage
                    │           → control returns to orchestrator
                    │
                    ├─ calls lookup_event(url)
                    │     → direct ticket_lookup scrape
                    │     → result added as ToolMessage
                    │     → control returns to orchestrator
                    │
                    └─ no tool calls → END (respond to user)
```

## Why This Architecture

### Problem diagnosis

The current deep agent fails because:

1. **Model hallucinates instead of calling tools** — llama-4-scout narrates tool use ("I'll search for...") then lists fake events
2. **When it does call tools, queries are garbage** — too broad, no decomposition
3. **No validation** — never verifies events are real
4. **No self-reflection** — stops after one search attempt
5. **4 redundant tools confuse the model** — event_search vs firecrawl_search overlap

### How the pipeline fixes each problem

| Problem | Fix |
|---------|-----|
| Model hallucinates results | LLM only decides IF to search; pipeline produces results deterministically |
| Bad search queries | Search Planner (separate LLM) decomposes into targeted queries with domain knowledge |
| No validation | Validator scrapes top results to verify they're real |
| No reflection | Orchestrator sees synthesized results and can trigger another search |
| Redundant tools | Orchestrator has exactly 2 tools; pipeline calls search APIs directly |

## State

```python
class M6State(TypedDict):
    messages: Annotated[list, add_messages]  # Full chat history
    tool_rounds: int                         # Orchestrator loop counter
    done: bool                               # Termination flag
    current_query: str                       # Extracted user intent for pipeline
    search_plan: list[dict]                  # [{query, strategy, tool}]
    raw_results: list[dict]                  # Deduplicated search results
    validated_results: list[dict]            # Verified events with details
```

## Nodes

### 1. orchestrator

- **Type**: ReAct agent (LLM with tools)
- **Model**: `meta-llama/llama-4-scout-17b-16e-instruct`
- **Tools**: `search_events(query, city)`, `lookup_event(url)`
- **Behavior**: Manages conversation. When user asks about events, calls `search_events`. When user provides a specific URL, calls `lookup_event`. When it has enough context, responds directly.
- **Anti-hallucination**: Prompt explicitly forbids fabricating event details. The model can only present what came from the pipeline.
- **Max tool rounds**: 3 (not 10 — the pipeline does the heavy lifting)

### 2. search_planner

- **Type**: Single LLM call, structured JSON output
- **Model**: `llama-3.1-8b-instant`
- **Input**: `current_query` from state
- **Output**: `search_plan` — list of 5-8 search objects
- **Domain knowledge baked into prompt**: Artist rosters by subgenre, major venues by city, promoter/platform mappings, effective search strategies

Example output for "mainstream melodic EDM bay area":
```json
[
  {"query": "Illenium San Francisco 2026 concert tickets", "strategy": "artist", "tool": "event_search"},
  {"query": "ODESZA Bay Area 2026 tour dates", "strategy": "artist", "tool": "event_search"},
  {"query": "Seven Lions upcoming shows San Francisco", "strategy": "artist", "tool": "event_search"},
  {"query": "Above & Beyond Bay Area 2026", "strategy": "artist", "tool": "event_search"},
  {"query": "Insomniac events Bay Area 2026", "strategy": "promoter", "tool": "firecrawl_search"},
  {"query": "Bill Graham Civic Auditorium EDM shows 2026", "strategy": "venue", "tool": "event_search"},
  {"query": "The Midway SF electronic music events", "strategy": "venue", "tool": "firecrawl_search"},
  {"query": "Bay Area EDM festivals summer 2026", "strategy": "genre", "tool": "event_search"}
]
```

### 3. search_executor

- **Type**: Pure function (no LLM)
- **Execution**: `asyncio.gather` with semaphore (max 3 concurrent Firecrawl calls)
- **For each search in plan**: calls EventSearch or FirecrawlSearch based on `tool` field
- **Deduplication**: by URL
- **Error handling**: retry once with 2s backoff on 429. Log failures, continue with partial results. If ALL searches fail, set `raw_results` to empty list with a `search_failed: True` flag.
- **Output**: `raw_results` — up to 15 deduplicated results

### 4. validator

- **Type**: Pure function (no LLM)
- **Input**: top 8 from `raw_results`
- **Execution**: `asyncio.gather` with semaphore (max 3 concurrent) — runs `ticket_lookup` on each
- **Filtering**: removes 404s, empty scrapes, clearly outdated events
- **Content truncation**: 3000 chars per scrape (down from 6000) to limit prompt injection surface
- **Output**: `validated_results` — verified events with scraped details

### 5. synthesizer

- **Type**: Single LLM call
- **Model**: `qwen/qwen3-32b`
- **Input**: `validated_results` + `current_query` + brief conversation context
- **Output**: Natural language response added to `messages` as an AIMessage
- **Behavior**: Ranks by relevance, includes ticket links/prices/dates, attributes sources, is opinionated. If validated_results is empty, says so and suggests broadening the search.
- **Context isolation**: only sees validated results + query, NOT full chat history (keeps token count ~2000)

## LangGraph Wiring

```python
START → "orchestrator"

"orchestrator" → route_action:
    "search_pipeline" → "search_planner"     # orchestrator called search_events
    "direct_lookup"   → "tool_executor"       # orchestrator called lookup_event
    "respond"         → END                   # no tool calls

"search_planner" → "search_executor" → "validator" → "synthesizer" → "orchestrator"
"tool_executor" → "orchestrator"
```

### Routing logic

```python
def route_action(state: M6State) -> str:
    last_msg = state["messages"][-1]
    if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
        return "respond"
    for tc in last_msg.tool_calls:
        if tc["name"] == "search_events":
            return "search_pipeline"
    return "direct_lookup"
```

### Termination conditions

```python
MAX_ORCHESTRATOR_ROUNDS = 3

def should_continue(state: M6State) -> str:
    if state.get("done", False):
        return "end"
    if state.get("tool_rounds", 0) >= MAX_ORCHESTRATOR_ROUNDS:
        return "end"
    return "continue"
```

## Model Distribution (TPM Management)

| Node | Model | Groq TPM Pool | Est. tokens/turn |
|------|-------|---------------|------------------|
| orchestrator | llama-4-scout-17b | Pool A | ~1500 (system + messages + response) |
| search_planner | llama-3.1-8b-instant | Pool B | ~500 (short prompt + JSON output) |
| synthesizer | qwen/qwen3-32b | Pool C | ~2500 (validated results + response) |

Three different models = three separate 6K TPM budgets. No single model exceeds 3K tokens/turn. Collision-free.

## New Agent Prompts

### deep_orchestrator.md

Conversational nightlife concierge. Manages the chat. Has 2 tools: search_events, lookup_event. Key rules:
- NEVER fabricate event details — only present what came from search results
- Call search_events when user asks about events/tickets
- Call lookup_event when user provides a specific URL
- After receiving search results, evaluate quality. If poor, search again with different angle.
- Be conversational, opinionated, remember context across turns

### search_planner.md

Query decomposition expert. Takes a natural language event request and outputs a JSON array of 5-8 targeted search queries. Domain knowledge includes:
- Major EDM artists by subgenre (melodic bass, house, techno, trance, etc.)
- Major venues by city (SF: Bill Graham, The Midway, Public Works, The Great Northern, etc.)
- Key promoters/platforms (Insomniac, Goldenvoice, HARD Events, etc.)
- Search strategies: by artist, by venue, by promoter, by genre, by date

### search_synthesizer.md

Results presenter. Takes validated event data and user's query. Outputs ranked recommendations with:
- Event name, date, venue, city
- Ticket prices and direct purchase links
- Artist/lineup highlights
- Source attribution (RA, Eventbrite, Dice, etc.)
- Opinionated takes ("This one's the move", "Skip this — overpriced")
- Fallback behavior when no results found

## Config Changes

### models.yaml additions
```yaml
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

### tools.yaml additions
```yaml
deep_orchestrator:
  - search_events
  - lookup_event

search_planner: []
search_synthesizer: []
```

Note: `search_events` and `lookup_event` are "virtual tools" — the orchestrator sees them as callable tools, but the graph routes to pipeline nodes instead of executing them directly.

## Error Handling

| Failure | Handling |
|---------|----------|
| Firecrawl 429 (rate limit) | Retry once with 2s backoff, then skip that query |
| Firecrawl 5xx / timeout | Skip that query, continue with partial results |
| ALL searches fail | Set `search_failed` flag, synthesizer says "search is down, try again" |
| Validator filters everything | Synthesizer says "couldn't verify results, here's what I found unverified" with caveat |
| Search planner returns bad JSON | Fallback: single broad event_search with original query |
| Groq 429 on any model | Caught at node level, returns graceful error message |
| Endpoint timeout | `asyncio.wait_for(graph.ainvoke(...), timeout=60)` |

## Files Changed

| File | Change |
|------|--------|
| `graph/m6/state.py` | Add pipeline fields: current_query, search_plan, raw_results, validated_results |
| `graph/m6/nodes.py` | Rewrite: 5 node functions (orchestrator, search_planner, search_executor, validator, synthesizer) + tool_executor + routing |
| `graph/m6/workflow.py` | New graph topology with pipeline edges |
| `graph/m6/conditions.py` | New routing + termination logic |
| `agents/deep_orchestrator.md` | New prompt (replaces deep_agent.md) |
| `agents/search_planner.md` | New prompt |
| `agents/search_synthesizer.md` | New prompt |
| `config/models.yaml` | Add deep_orchestrator, search_planner, search_synthesizer |
| `config/tools.yaml` | Update tool assignments |
| `graph/common.py` | Fix _execute_tool_calls to use asyncio.gather (parallel) |
| `tools/events.py` | Parallelize internal searches, add retry logic, fix success=True on failure |
| `api/main.py` | Add endpoint timeout, update to use new graph |
| `vizlang/m6.py` | Update if needed for new graph |
| `docs/lessons/m6/README.md` | Update lesson doc for new architecture |

## Known Limitations (workshop scope)

- **MemorySaver**: Chat sessions lost on restart. Production would use PostgresSaver.
- **No streaming**: Responses appear all at once. Production would use SSE.
- **No cancel**: Long searches can't be interrupted.
- **No auth**: API is open. Production needs auth + rate limiting.
- **CORS wildcard**: Localhost only.
- **No concurrency guards**: Single-user demo. Production needs locks.

## Decision Log

| Decision | Alternatives Considered | Resolution |
|----------|------------------------|------------|
| Pipeline architecture over enhanced single-agent | Better prompt alone, smarter tools only | Pipeline eliminates hallucination by design; prompt improvements are necessary but not sufficient for llama-4-scout |
| 3 models on 3 TPM pools | Single model with aggressive trimming | Model distribution is the only way to stay within 6K TPM per model on free tier |
| Orchestrator has 2 tools (search_events, lookup_event) | 4 tools (current), 0 tools (pure routing) | 2 tools gives flexibility for ad-hoc lookups without confusing tool selection |
| Semaphore (max 3) on Firecrawl calls | Unlimited parallel, fully sequential | 3 concurrent balances speed vs rate-limit risk |
| 3000 char scrape truncation (down from 6000) | No truncation, 1000 chars | 3000 gives enough event detail while limiting injection surface and token usage |
| MAX_ORCHESTRATOR_ROUNDS = 3 (down from 10) | Keep 10, reduce to 1 | 3 allows one search + one refinement + one response. 10 was burning TPM for no benefit. |
