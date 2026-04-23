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


from graph.m6.conditions import route_action, should_stop


def _make_ai_msg(content="hello", tool_calls=None):
	from langchain_core.messages import AIMessage
	if tool_calls:
		return AIMessage(content=content, tool_calls=tool_calls)
	return AIMessage(content=content)


def test_route_action_no_tools():
	state = {"messages": [_make_ai_msg("hi")], "tool_rounds": 0, "done": False}
	assert route_action(state) == "respond"


def test_route_action_search_events():
	tc = [{"name": "search_events", "args": {"query": "edm", "city": "SF"}, "id": "1"}]
	state = {"messages": [_make_ai_msg("searching", tc)], "tool_rounds": 0, "done": False}
	assert route_action(state) == "search_pipeline"


def test_route_action_lookup_event():
	tc = [{"name": "lookup_event", "args": {"url": "https://ra.co/events/123"}, "id": "1"}]
	state = {"messages": [_make_ai_msg("looking up", tc)], "tool_rounds": 0, "done": False}
	assert route_action(state) == "direct_lookup"


def test_should_stop_when_done():
	state = {"done": True, "tool_rounds": 1}
	assert should_stop(state) == "end"


def test_should_stop_max_rounds():
	state = {"done": False, "tool_rounds": 3}
	assert should_stop(state) == "end"


def test_should_stop_continues():
	state = {"done": False, "tool_rounds": 1}
	assert should_stop(state) == "continue"


def test_m6_graph_compiles():
    from graph.m6.workflow import build_graph
    g = build_graph()
    node_names = set(g.nodes.keys()) - {"__start__"}
    assert "orchestrator" in node_names
    assert "search_planner" in node_names
    assert "search_executor" in node_names
    assert "validator" in node_names
    assert "synthesizer" in node_names
    assert "tool_executor" in node_names


def test_m6_async_graph_compiles():
    from graph.m6.workflow import build_async_graph
    g = build_async_graph()
    node_names = set(g.nodes.keys()) - {"__start__"}
    assert "orchestrator" in node_names
    assert "search_planner" in node_names
