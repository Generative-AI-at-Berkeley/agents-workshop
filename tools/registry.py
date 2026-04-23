from __future__ import annotations

import yaml

from graph.common import CONFIG_DIR
from tools.base import BaseTool
from tools.firecrawl import FirecrawlSearch, FirecrawlScrape

_ALL_TOOLS: dict[str, type[BaseTool]] = {"firecrawl_search": FirecrawlSearch, "firecrawl_scrape": FirecrawlScrape}


def _load_tools_config() -> dict:
	with open(CONFIG_DIR / "tools.yaml") as f:
		return yaml.safe_load(f)


def get_tools_for_agent(agent_name: str) -> list[BaseTool]:
	cfg = _load_tools_config()
	agent_tools = cfg.get("agents", {}).get(agent_name, [])
	return [_ALL_TOOLS[name]() for name in agent_tools if name in _ALL_TOOLS]
