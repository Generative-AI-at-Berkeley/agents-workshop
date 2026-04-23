FROM python:3.13-slim

WORKDIR /app

RUN --mount=from=ghcr.io/astral-sh/uv:0.8,source=/uv,target=/bin/uv \
    --mount=source=pyproject.toml,target=pyproject.toml \
    --mount=source=uv.lock,target=uv.lock \
    --mount=type=cache,target=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/usr/local uv sync --no-install-project --frozen

COPY . .

EXPOSE 8200

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8200"]
