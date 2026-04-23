from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from config.settings import get_settings
from tools.base import BaseTool, ToolResult

log = structlog.get_logger(__name__)

_FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"


def _headers() -> dict[str, str]:
	settings = get_settings()
	return {"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}", "Content-Type": "application/json"}


class EventSearch(BaseTool):
	name = "event_search"
	description = (
		"Search for upcoming events, concerts, raves, and parties in a specific city. "
		"Aggregates results from multiple sources including RA, Eventbrite, Dice, and local listings. "
		"Use this to find real events with dates, venues, and ticket links."
	)

	async def run(self, *, city: str, query: str, date: str = "", **_kwargs: Any) -> ToolResult:
		log.info("event_search", city=city, query=query, date=date)
		search_queries = [
			f"{query} events {city} {date} tickets site:ra.co OR site:dice.fm OR site:eventbrite.com",
			f"{query} {city} {date} upcoming events tickets",
		]
		all_results: list[dict] = []
		seen_urls: set[str] = set()

		async def _search_one(sq: str) -> list[dict]:
			for attempt in range(2):
				async with httpx.AsyncClient(timeout=30) as client:
					resp = await client.post(
						f"{_FIRECRAWL_BASE}/search", headers=_headers(), json={"query": sq, "limit": 5}
					)
				if resp.status_code == 429 and attempt == 0:
					log.warning("event_search_rate_limited", query=sq, attempt=attempt)
					await asyncio.sleep(2)
					continue
				if resp.status_code != 200:
					log.warning("event_search_failed", query=sq, status=resp.status_code)
					return []
				data = resp.json()
				return [
					{
						"title": r.get("title", ""),
						"url": r.get("url", ""),
						"snippet": r.get("description", r.get("snippet", "")),
						"source": _detect_source(r.get("url", "")),
					}
					for r in data.get("data", [])
				]
			return []

		batch_results = await asyncio.gather(*[_search_one(sq) for sq in search_queries])
		for batch in batch_results:
			for entry in batch:
				if entry["url"] not in seen_urls:
					seen_urls.add(entry["url"])
					all_results.append(entry)

		if not all_results and not any(batch_results):
			return ToolResult(tool_name=self.name, success=False, error="All search queries failed or returned no results")

		return ToolResult(tool_name=self.name, success=True, data=all_results[:10])

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {
				"city": {"type": "string", "description": "City to search events in"},
				"query": {"type": "string", "description": "Event type or artist, e.g. 'techno rave', 'house music'"},
				"date": {"type": "string", "description": "Date or date range, e.g. 'this saturday', 'june 2026'"},
			},
			"required": ["city", "query"],
		}


class TicketLookup(BaseTool):
	name = "ticket_lookup"
	description = (
		"Scrape a specific event page to extract ticket details: price tiers, availability, "
		"lineup, doors/set times, venue info, and direct purchase links. "
		"Works with RA, Dice, Eventbrite, and most event pages."
	)

	async def run(self, *, url: str, **_kwargs: Any) -> ToolResult:
		log.info("ticket_lookup", url=url)
		async with httpx.AsyncClient(timeout=30) as client:
			resp = await client.post(
				f"{_FIRECRAWL_BASE}/scrape", headers=_headers(), json={"url": url, "formats": ["markdown"]}
			)
			if resp.status_code != 200:
				return ToolResult(
					tool_name=self.name, success=False, error=f"HTTP {resp.status_code}: {resp.text[:500]}"
				)
			data = resp.json()

		content = data.get("data", {}).get("markdown", "")
		if len(content) > 6000:
			content = content[:6000] + "\n\n[truncated]"

		return ToolResult(
			tool_name=self.name,
			success=True,
			data={"url": url, "source": _detect_source(url), "content": content},
		)

	def _parameters(self) -> dict:
		return {
			"type": "object",
			"properties": {"url": {"type": "string", "description": "Event or ticket page URL to scrape"}},
			"required": ["url"],
		}


def _detect_source(url: str) -> str:
	url_lower = url.lower()
	for source in ["ra.co", "dice.fm", "eventbrite", "shotgun", "tixr", "seetickets", "ticketmaster"]:
		if source in url_lower:
			return source
	return "other"
