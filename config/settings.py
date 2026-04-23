from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=_PROJECT_ROOT / ".env", extra="ignore")

	# LLM providers
	GROQ_API_KEY: str | None = None

	# Tools
	FIRECRAWL_API_KEY: str | None = None

	# Langfuse
	LANGFUSE_PUBLIC_KEY: str | None = None
	LANGFUSE_SECRET_KEY: str | None = None
	LANGFUSE_HOST: str = "http://localhost:3200"


def get_settings() -> Settings:
	return Settings()
