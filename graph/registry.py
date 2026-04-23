from __future__ import annotations

MODULES = {
	1: "graph.m1.workflow",
	2: "graph.m2.workflow",
	3: "graph.m3.workflow",
	4: "graph.m4.workflow",
	5: "graph.m5.workflow",
}

DEFAULT_MODULE = 5


def build_graph(module: int = DEFAULT_MODULE):
	"""Sync graph — used by VizLang."""
	import importlib

	wf = importlib.import_module(MODULES[module])
	return wf.build_graph()


def build_async_graph(module: int = DEFAULT_MODULE):
	"""Async graph — used by CLI and API."""
	import importlib

	wf = importlib.import_module(MODULES[module])
	return wf.build_async_graph()


def initial_state(module: int, request) -> dict:
	base: dict = {"request": request, "messages": [], "itinerary": None}
	if module >= 2:
		base |= {"plan": "", "raw_research": "", "review_passed": False, "review_feedback": "", "attempts": 0}
	if module >= 4:
		base["scout_assignments"] = []
	if module >= 5:
		base["merged_research"] = ""
	return base
