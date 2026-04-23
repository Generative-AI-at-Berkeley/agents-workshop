# agents-workshop

AI agents workshop project.

## Build, lint, test commands

- Install deps (host): `mise run install-host`  (or `uv sync`)
- Start stack: `mise run dev`  (or `docker compose up`)
- Stop stack: `mise run down`
- Tail logs: `mise run logs`
- Shell into API container: `mise run shell`
- Run API (host): `mise run api`
- Lint: `mise run lint`  (ruff check + format check + ty)
- Format: `mise run format`
- Tests: `mise run test`  (or `uv run pytest`)
- Run single test: `uv run pytest tests/test_foo.py::test_bar`

## Ports

| Service | Host port |
|---|---|
| workshop API | 8200 |
| Langfuse web | 3200 |
| Langfuse postgres | 5435 |
| Langfuse clickhouse | 8125 / 9005 |
| Langfuse redis | 6381 |
| Langfuse minio | 9200 / 9201 |

## Project structure

- **agents/** — LLM system prompts as markdown. One file = one agent.
- **tools/** — stateless wrappers around external APIs.
- **models/** — LLM provider abstractions.
- **schemas/** — Pydantic v2 models for every typed boundary.
- **graph/** — LangGraph orchestration (workflow, nodes, conditions).
- **config/** — `models.yaml`, `tools.yaml`, `settings.py`.
- **scripts/** — deterministic utilities (not LLM calls).
- **api/** — FastAPI wrapper around the graph.
- **tests/** — pytest suite.

## Code conventions

- Python 3.13, `uv` for deps, `mise` for tasks.
- Pydantic v2 for all schemas. No `Any` except where truly unavoidable.
- Async throughout — all tool calls, model calls, graph nodes.
- Use `httpx`, never `requests` (enforced by ruff banned-api).
- `structlog` for logs.
- Ruff config: 120 cols, tab indent, `select = ['ASYNC', 'F', 'FAST', 'PLE', 'PT', 'SIM', 'TID', 'UP045']`.
- No hardcoded agent/tool/model names in code — pull from `config/*.yaml`.

## Observability

Langfuse runs locally (see compose). Every workflow run is a trace; every agent
call is a span; every LLM call is a generation. Keys auto-seed on first boot via
`LANGFUSE_INIT_*` env vars — the values in `.env.example` already match, so tracing
works out of the box. Run `mise run langfuse-ui` for the UI URL + seeded login.
