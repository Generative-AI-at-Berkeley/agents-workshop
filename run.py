import asyncio
import contextlib
import json
import sys
from pathlib import Path
from uuid import uuid4

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from graph.registry import build_async_graph, initial_state
from observability import trace_context
from schemas.nightout import NightOutRequest

_SESSION_MIN_MODULE = 3

log = structlog.get_logger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


async def main(request: NightOutRequest, module: int) -> None:
	run_id = uuid4().hex[:12]
	log.info("run_start", run_id=run_id, module=module, city=request.city, vibe=request.vibe)

	use_session = module >= _SESSION_MIN_MODULE
	ctx = (
		trace_context(run_id=run_id, name=f"nightout-m{module}", module=module, input=request.model_dump())
		if use_session
		else contextlib.nullcontext()
	)
	with ctx:
		graph = build_async_graph(module)
		result = await graph.ainvoke(initial_state(module, request))

	itinerary = result["itinerary"]
	out_path = OUTPUT_DIR / f"{run_id}.json"
	out_path.write_text(json.dumps(itinerary.model_dump(), indent=2))

	log.info("run_complete", run_id=run_id, output=str(out_path))
	print(json.dumps(itinerary.model_dump(), indent=2))


async def chat(initial_message: str | None = None) -> None:
	session_id = uuid4().hex[:12]
	graph = build_async_graph(6)
	config = {"configurable": {"thread_id": session_id}}

	print("M6 Search Orchestra Chat (type 'quit' to exit)")
	print("=" * 50)

	if initial_message:
		msg = initial_message
	else:
		msg = (await asyncio.to_thread(input, "\nYou: ")).strip()

	while msg and msg.lower() not in ("quit", "exit", "q"):
		initial_state = {
			"messages": [HumanMessage(content=msg)],
			"tool_rounds": 0,
			"done": False,
			"current_query": "",
			"search_plan": [],
			"raw_results": [],
			"validated_results": [],
		}

		with trace_context(run_id=session_id, name="nightout-m6-chat", module=6, input=msg):
			result = await graph.ainvoke(initial_state, config=config)

		for m in reversed(result["messages"]):
			if isinstance(m, AIMessage) and m.content:
				print(f"\nAgent: {m.content}")
				break

		print()
		msg = (await asyncio.to_thread(input, "You: ")).strip()

	print("Goodbye!")


if __name__ == "__main__":
	module = 2
	args = sys.argv[1:]

	if args and args[0].startswith("--module"):
		if "=" in args[0]:
			module = int(args[0].split("=")[1])
			args = args[1:]
		else:
			module = int(args[1])
			args = args[2:]

	if module == 6:
		initial_msg = " ".join(args) if args else None
		asyncio.run(chat(initial_msg))
	else:
		city = args[0] if len(args) > 0 else "berlin"
		vibe = args[1] if len(args) > 1 else "techno, dark, underground"
		date = args[2] if len(args) > 2 else "this saturday"
		group_size = int(args[3]) if len(args) > 3 else 4

		request = NightOutRequest(city=city, vibe=vibe, date=date, group_size=group_size)
		asyncio.run(main(request, module))
