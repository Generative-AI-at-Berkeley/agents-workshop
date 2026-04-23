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

## Commands

- `mise run dev` — start docker compose
- `mise run down` — stop
- `mise run logs` — tail logs
- `mise run api` — run API on host
- `mise run lint` — ruff check + format check + ty
- `mise run format` — autofix
- `mise run test` — pytest
- `mise run langfuse-ui` — print Langfuse URL + credentials
