import asyncio
from unittest.mock import AsyncMock, patch

from config.settings import get_settings


def test_settings_cached():
	s1 = get_settings()
	s2 = get_settings()
	assert s1 is s2


def test_event_search_reports_failure_when_all_fail():
	from tools.events import EventSearch

	tool = EventSearch()

	async def _run():
		with patch("tools.events.httpx.AsyncClient") as mock_client_cls:
			mock_client = AsyncMock()
			mock_client.__aenter__ = AsyncMock(return_value=mock_client)
			mock_client.__aexit__ = AsyncMock(return_value=False)
			mock_client.post = AsyncMock(
				return_value=AsyncMock(status_code=429, text="rate limited", json=lambda: {})
			)
			mock_client_cls.return_value = mock_client
			result = await tool.run(city="SF", query="test")
		return result

	result = asyncio.run(_run())
	assert result.success is False
