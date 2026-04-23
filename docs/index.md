---
layout: default
title: Agents Workshop
---

# Agents Workshop

Build production AI agents, one pattern at a time. A hands-on workshop by **Generative AI at Berkeley**.

We build a **Night Out Agent** six times — each module adds a real production pattern.

## Modules

| Module | Pattern | What you learn |
|--------|---------|----------------|
| [Overview](lessons/overview/) | — | The workshop arc and tech stack |
| [M1](lessons/m1/) | Single LLM call | One call is an agent. Observability makes it debuggable. |
| [M2](lessons/m2/) | Directed graph + retry | The graph IS the product spec. 90% of production agents. |
| [M3](lessons/m3/) | Tool use + RBAC | Without RBAC, every agent can do everything. |
| [M4](lessons/m4/) | Manager + subagents | The manager doesn't work — it delegates. |
| [M5](lessons/m5/) | Parallel fan-out + merge | Fan-out is easy. Merge is the product. |
| [M6](lessons/m6/) | Multi-agent search orchestra | When a single agent hallucinates, redesign the architecture. |

## Setup

```bash
git clone <repo-url> && cd agents-workshop
cp .env.example .env        # add your GROQ_API_KEY and FIRECRAWL_API_KEY
uv sync                     # install Python deps
docker compose up            # start Langfuse + API
```

See the full [setup guide on GitHub](https://github.com/generative-ai-at-berkeley/agents-workshop#setup).

## Tech Stack

| Layer | Tool |
|-------|------|
| Orchestration | LangGraph |
| LLM | Groq (free tier) |
| Observability | Langfuse (self-hosted) |
| Tools | Firecrawl |
| Schemas | Pydantic v2 |
| API | FastAPI |
