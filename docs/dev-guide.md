# Dev Guide

Day-to-day workflows for the agents workshop. Companion to [README.md](../README.md) (setup) and [CLAUDE.md](../CLAUDE.md) (conventions).

---

## The stack at a glance

One `mise run dev` brings up 7 containers. Only one is ours.

| Service | Owner | Purpose | Host port |
|---|---|---|---|
| `workshop-api` | us | FastAPI wrapper around the graph | 8200 |
| `langfuse-web` | Langfuse | UI + REST API | 3200 |
| `langfuse-worker` | Langfuse | async event processing | — |
| `langfuse-db` | Langfuse | OLTP (orgs, projects, prompts) | 5435 |
| `langfuse-clickhouse` | Langfuse | traces / generations / observations | 8125, 9005 |
| `langfuse-redis` | Langfuse | queue between web and worker | 6381 |
| `langfuse-minio` | Langfuse | blob storage for event payloads | 9200, 9201 |

First boot runs migrations + seeds the org/project/keys — takes 60-90s. Subsequent boots are fast.

---

## mise tasks cheat sheet

| Task | What it does |
|---|---|
| `mise install` | Installs Python 3.13 + uv 0.8 (one time) |
| `mise run install-host` | `uv sync` on the host — needed for IDE tooling |
| `mise run dev` | `docker compose up` — foreground, Ctrl+C to stop |
| `mise run down` | `docker compose down` — preserves volumes |
| `mise run restart` | Restart all containers |
| `mise run logs` | Tail logs without stopping the stack |
| `mise run shell` | Bash into the `workshop-api` container |
| `mise run psql-langfuse` | `psql` into Langfuse's postgres |
| `mise run langfuse-ui` | Print the UI URL + seeded login |
| `mise run api` | Run FastAPI on the host (port 8200) with `--reload` |
| `mise run plan -- "city" "vibe" "date" group_size` | Run the CLI planner |
| `mise run lint` | `ruff check` + `ruff format --check` + `ty check` |
| `mise run format` | Autofix: `ruff check --fix` + `ruff format` |
| `mise run test` | `pytest` |
| `mise run ui-install` | Install UI npm deps |
| `mise run ui` | Run the UI dev server on :5174 |
| `mise run ui-build` | Production build of the UI |

---

## First-time setup

```bash
# 1. Install mise tooling (Python 3.13 + uv)
mise install

# 2. Install Python deps on the host
mise run install-host

# 3. Copy env and add your API keys
cp .env.example .env
# Edit .env — at minimum set GROQ_API_KEY

# 4. Install UI deps
mise run ui-install

# 5. Start the full stack
mise run dev

# 6. In another terminal, run the UI
mise run ui
```

---

## Common workflows

### Plan a night out (CLI)

```bash
mise run plan -- "berlin" "techno, dark, underground" "this saturday" 4
```

### Hit the API

```bash
curl -X POST http://localhost:8200/runs \
  -H 'content-type: application/json' \
  -d '{"city": "berlin", "vibe": "techno", "date": "this saturday", "group_size": 4}'
```

### View a trace in Langfuse

1. `mise run langfuse-ui` — prints URL + login
2. Log into `http://localhost:3200`
3. Traces appear in the `agents-workshop` project

### Run one test

```bash
uv run pytest tests/test_schemas.py::test_name -v
```

---

## Environment variables

Everything lives in `.env` (copy from `.env.example`). Only `GROQ_API_KEY` is required to run the planner.

| Var | Required for | Default |
|---|---|---|
| `GROQ_API_KEY` | All LLM calls | — |
| `FIRECRAWL_API_KEY` | Search/scrape tools (Module 3+) | — |
| `LANGFUSE_PUBLIC_KEY` | tracing | `pk-lf-workshop-local-dev` (auto-seeded) |
| `LANGFUSE_SECRET_KEY` | tracing | `sk-lf-workshop-local-dev` (auto-seeded) |
| `LANGFUSE_HOST` | tracing | `http://localhost:3200` |

---

## Adding agents, tools, and models

### Add a new agent

1. Create `agents/<agent_name>.md` — the markdown IS the system prompt
2. Add the agent to `config/models.yaml` with its provider + model
3. If it needs tools, grant access in `config/tools.yaml`
4. Add a node function in `graph/nodes.py` and wire it into `graph/workflow.py`

### Add a new tool

1. Create `tools/<tool_name>.py` inheriting the base tool class
2. Register it in `config/tools.yaml` with visibility (`public` or `private`)

---

## Troubleshooting

### "Port already in use"

```bash
lsof -iTCP:8200 -sTCP:LISTEN
```

### Langfuse seeded creds don't work

Seed only runs on an empty database. Nuke volumes and restart:

```bash
mise run down
docker volume rm agents-workshop_langfuse_postgres agents-workshop_langfuse_clickhouse_data agents-workshop_langfuse_minio
mise run dev
```

### First `mise run dev` hangs for a minute

Normal — Langfuse runs migrations on first boot.

### `.env` changes not picked up

```bash
mise run restart
```

---

## IDE setup

### VS Code

1. Python interpreter: `./venv/bin/python` (after `mise run install-host`)
2. Extensions: `ms-python.python`, `charliermarsh.ruff`
3. Pyright picks up `pyrightconfig.json` automatically
