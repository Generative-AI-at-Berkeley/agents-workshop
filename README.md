# agents-workshop

Build production AI agents, one pattern at a time. A hands-on workshop by **Generative AI at Berkeley**.

We build a **Night Out Agent** six times — each module adds a real production pattern (directed graphs, tool use, RBAC, subagents, parallel fan-out, multi-agent search).

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.13 | [python.org](https://www.python.org/downloads/) or `brew install python@3.13` |
| Docker | 24+ | [docker.com](https://docs.docker.com/get-docker/) |
| uv | 0.8+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

**Optional but recommended:**
- [mise](https://mise.jdx.dev/) — task runner that wraps all commands below. Install: `curl https://mise.jdx.dev/install.sh | sh`
- [jq](https://jqlang.github.io/jq/) — pretty-prints JSON API responses. Install: `brew install jq`

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url> && cd agents-workshop

# With mise (recommended)
mise run install-host

# Without mise
uv sync
```

### 2. Get your API keys

You need two free API keys:

| Key | Get it at | Free tier |
|-----|-----------|-----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | 6K TPM per model |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://www.firecrawl.dev/) | 500 credits/month (see below for 20K) |

**Firecrawl student credits:** Sign up with your `@berkeley.edu` email, then go to **Billing** and enter promo code **`STUDENTEDU`** for 20K free credits.

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and paste your keys:

```bash
GROQ_API_KEY=gsk_...
FIRECRAWL_API_KEY=fc-...
```

The Langfuse keys are pre-filled and auto-seeded on first boot — no manual setup needed.

### 4. Start the stack

```bash
# With mise
mise run dev

# Without mise
docker compose up
```

This starts:
- **Workshop API** on `http://localhost:8200`
- **Langfuse** (observability UI) on `http://localhost:3200`

First boot takes ~2 minutes to pull images and seed the database.

### 5. Verify it works

```bash
# Run M1 (simplest module) to verify everything connects
uv run python run.py --module 1 "berlin" "techno, underground"
```

You should see a JSON itinerary printed to stdout. If you get an API key error, double-check your `.env`.

## Running modules

### M1-M5: One-shot planning (request in, itinerary out)

```bash
# CLI
uv run python run.py --module 2 "san francisco" "house music, rooftop" "this saturday" 4

# API
curl -s -X POST http://localhost:8200/runs \
  -H "Content-Type: application/json" \
  -d '{"city": "san francisco", "vibe": "house music", "module": 5}' | jq
```

### M6: Search Orchestra (multi-turn chat)

```bash
# Interactive chat
uv run python run.py --module 6

# One-liner
uv run python run.py --module 6 "find me melodic EDM shows in the bay area"

# API — create a session, then send messages
SESSION=$(curl -s -X POST http://localhost:8200/chat | jq -r .session_id)

curl -s -X POST "http://localhost:8200/chat/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "find me raves in SF this weekend"}' | jq .assistant_message.content

# Follow up (agent remembers context)
curl -s -X POST "http://localhost:8200/chat/$SESSION/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "what about afterhours?"}' | jq .assistant_message.content
```

## Observability (Langfuse)

Every agent call is traced. Open `http://localhost:3200` and log in:

```
Email:    admin@berkeleydegenerative.ai
Password: agentsworkshoplocal
```

Or run `mise run langfuse-ui` to print the credentials.

## Commands reference

| With mise | Without mise | What it does |
|-----------|-------------|--------------|
| `mise run dev` | `docker compose up` | Start full stack |
| `mise run down` | `docker compose down` | Stop stack |
| `mise run logs` | `docker compose logs -f` | Tail logs |
| `mise run api` | `uv run uvicorn api.main:app --reload --port 8200` | Run API on host (no Docker) |
| `mise run test` | `uv run pytest` | Run tests |
| `mise run lint` | `uv run ruff check && uv run ruff format --check` | Lint |
| `mise run format` | `uv run ruff check --fix && uv run ruff format` | Autofix lint |

## Project structure

```
agents-workshop/
  agents/           # System prompts (one .md per agent)
  graph/
    common.py       # Shared: call_agent(), tool loop, helpers
    registry.py     # Module dispatcher
    m1/ ... m6/     # Each module: state, nodes, conditions, workflow
  tools/            # Firecrawl + event search wrappers
  config/
    models.yaml     # Agent → model mapping
    tools.yaml      # Agent → tool permissions (RBAC)
  schemas/          # Pydantic v2 models
  observability.py  # Langfuse tracing
  api/              # FastAPI server
  run.py            # CLI runner
  docs/lessons/     # Per-module architecture lessons
```

## Ports

| Service | Port |
|---------|------|
| Workshop API | 8200 |
| Langfuse UI | 3200 |

## Troubleshooting

**"GROQ_API_KEY not set" or 401 errors**
Check your `.env` file. The key should start with `gsk_`.

**"FIRECRAWL_API_KEY not set" or search returns no results**
Check your `.env` file. The key should start with `fc-`.

**Docker compose fails to start**
Make sure Docker is running. On first boot, it pulls ~2GB of images.

**Langfuse UI shows no traces**
The Langfuse keys in `.env.example` are pre-seeded — make sure you didn't change them. If you did, run `docker compose down -v && docker compose up` to reset.

**Rate limit errors (429)**
Groq's free tier has a 6K TPM limit per model. Wait 60 seconds and retry. M6 distributes load across 3 models to minimize this.

## Lessons

| Module | Lesson | Key idea |
|--------|--------|----------|
| Overview | [docs/lessons/overview](docs/lessons/overview/README.md) | The workshop arc |
| M1 | [docs/lessons/m1](docs/lessons/m1/README.md) | Single LLM call |
| M2 | [docs/lessons/m2](docs/lessons/m2/README.md) | Directed graph + retry |
| M3 | [docs/lessons/m3](docs/lessons/m3/README.md) | Tool use + RBAC |
| M4 | [docs/lessons/m4](docs/lessons/m4/README.md) | Manager + subagents |
| M5 | [docs/lessons/m5](docs/lessons/m5/README.md) | Parallel fan-out |
| M6 | [docs/lessons/m6](docs/lessons/m6/README.md) | Multi-agent search orchestra |
