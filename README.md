# agents-workshop

## Quick start

```bash
# Install mise + uv if you haven't
mise run install-host   # install Python deps on host

# Copy env and fill in your API keys
cp .env.example .env

# Start the full stack (Langfuse + API)
mise run dev
```

## Ports

| Service | Host port |
|---|---|
| workshop API | 8200 |
| Langfuse web | 3200 |
| Langfuse postgres | 5435 |
| Langfuse clickhouse | 8125 / 9005 |
| Langfuse redis | 6381 |
| Langfuse minio | 9200 / 9201 |

## M6: Search Orchestra (Chat Agent)

M6 is a multi-agent search pipeline with a conversational interface.

```bash
# CLI (interactive chat)
uv run python run.py --module 6

# CLI (one-liner)
uv run python run.py --module 6 "find me EDM shows in SF this weekend"

# API — create a session, then send messages
curl -s -X POST http://localhost:8200/chat | jq
# → {"session_id": "abc123", ...}

curl -s -X POST http://localhost:8200/chat/abc123/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "find me raves in SF this weekend"}' | jq

# Follow up (agent remembers context)
curl -s -X POST http://localhost:8200/chat/abc123/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "what about afterhours?"}' | jq
```

See [docs/lessons/m6/README.md](docs/lessons/m6/README.md) for the architecture lesson.

## Commands

- `mise run dev` — start docker compose
- `mise run down` — stop
- `mise run logs` — tail logs
- `mise run api` — run API on host
- `mise run lint` — ruff check + format check + ty
- `mise run format` — autofix
- `mise run test` — pytest
- `mise run langfuse-ui` — print Langfuse URL + credentials
