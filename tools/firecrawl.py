from __future__ import annotations

from typing import Any

import httpx
import structlog

from config.settings import get_settings
from tools.base import BaseTool, ToolResult

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.firecrawl.dev/v1"


def _headers() -> dict[str, str]:
	settings = get_settings()
	return {"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}", "Content-Type": "application/json"}


class FirecrawlSearch(BaseTool):
	name = "firecrawl_search"
	description = "Search the web for real-time information about venues, events, nightlife, and locations."

	async def run(self, *, query: str, limit: int = 5, **_kwargs: Any) -> ToolResult:
		log.info("firecrawl_search", query=query, limit=limit)
		async with httpx.AsyncClient(timeout=30) as client:
			resp = await client.post(f"{_BASE_URL}/search", headers=_headers(), json={"query": query, "limit": limit})
			if resp.status_code != 200:
				return ToolResult(
					tool_name=self.name, success=False, error=f"HTTP {resp.status_code}: {resp.text[:500]}"
				)
			data = resp.json()
		results = [
			{
				"title": r.get("title", ""),
				"url": r.get("url", ""),
				"snippet": r.get("description", r.get("snippet", "")),
			}
			for r in data.get("data", [])
		]
		return ToolResult(tool_name=self.name, success=True, data=results)

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "Search query"},
				"limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
			},
			"required": ["query"],
		}


class FirecrawlScrape(BaseTool):
	name = "firecrawl_scrape"
	description = (
		"Scrape a specific URL to extract its content as clean text. Use for venue pages, event listings, review sites."
	)

	async def run(self, *, url: str, **_kwargs: Any) -> ToolResult:
		log.info("firecrawl_scrape", url=url)
		async with httpx.AsyncClient(timeout=30) as client:
			resp = await client.post(
				f"{_BASE_URL}/scrape", headers=_headers(), json={"url": url, "formats": ["markdown"]}
			)
			if resp.status_code != 200:
				return ToolResult(
					tool_name=self.name, success=False, error=f"HTTP {resp.status_code}: {resp.text[:500]}"
				)
			data = resp.json()
		content = data.get("data", {}).get("markdown", data.get("data", {}).get("content", ""))
		if len(content) > 4000:
			content = content[:4000] + "\n\n[truncated]"
		return ToolResult(tool_name=self.name, success=True, data=content)

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {"url": {"type": "string", "description": "URL to scrape"}},
			"required": ["url"],
		}
