from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from graph.registry import build_async_graph, initial_state
from observability import trace_context
from schemas.nightout import Itinerary, NightOutRequest

log = structlog.get_logger(__name__)

app = FastAPI(title="agents-workshop", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _validate_keys() -> None:
	from config.settings import get_settings

	s = get_settings()
	missing = []
	if not s.GROQ_API_KEY:
		missing.append("GROQ_API_KEY")
	if not s.FIRECRAWL_API_KEY:
		missing.append("FIRECRAWL_API_KEY")
	if missing:
		log.warning("missing_api_keys", keys=missing, hint="cp .env.example .env and fill in your keys")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

_runs: dict[str, RunRecord] = {}
_results: dict[str, Itinerary] = {}

# --- M6 Chat State ---
_chat_graphs: dict[str, object] = {}
_chat_histories: dict[str, list[dict]] = {}


class RunRecord(BaseModel):
	run_id: str
	status: str
	created_at: str
	completed_at: str | None = None
	input: NightOutRequest
	module: int = 2
	error: str | None = None


class RunResponse(BaseModel):
	record: RunRecord
	itinerary: Itinerary | None = None


class CreateRunRequest(BaseModel):
	city: str
	vibe: str
	date: str
	group_size: int = 4
	notes: str = ""
	module: int = 2


@app.post("/runs")
async def create_run(req: CreateRunRequest) -> RunRecord:
	run_id = uuid4().hex[:12]
	now = datetime.now(timezone.utc).isoformat()

	night_req = NightOutRequest(city=req.city, vibe=req.vibe, date=req.date, group_size=req.group_size, notes=req.notes)

	record = RunRecord(run_id=run_id, status="running", created_at=now, input=night_req, module=req.module)
	_runs[run_id] = record

	asyncio.create_task(_execute_run(run_id, night_req, req.module))
	return record


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunResponse:
	record = _runs.get(run_id)
	if not record:
		raise HTTPException(status_code=404, detail="run not found")
	return RunResponse(record=record, itinerary=_results.get(run_id))


_SESSION_MIN_MODULE = 3


async def _execute_run(run_id: str, request: NightOutRequest, module: int) -> None:
	record = _runs[run_id]
	use_session = module >= _SESSION_MIN_MODULE
	ctx = (
		trace_context(run_id=run_id, name=f"nightout-m{module}", module=module, input=request.model_dump())
		if use_session
		else contextlib.nullcontext()
	)
	with ctx:
		try:
			graph = build_async_graph(module)
			result = await graph.ainvoke(initial_state(module, request))

			itinerary = result["itinerary"]
			_results[run_id] = itinerary

			out_path = OUTPUT_DIR / f"{run_id}.json"
			out_path.write_text(json.dumps(itinerary.model_dump(), indent=2))

			record.status = "completed"
			record.completed_at = datetime.now(timezone.utc).isoformat()
			log.info("run_complete", run_id=run_id, module=module)

		except Exception as exc:
			record.status = "failed"
			record.error = str(exc)
			record.completed_at = datetime.now(timezone.utc).isoformat()
			log.exception("run_failed", run_id=run_id)


# ──────────────────────────────────────────────
# M6 Chat Endpoints — Conversational Deep Agent
# ──────────────────────────────────────────────


class ChatMessage(BaseModel):
	role: str
	content: str
	timestamp: str | None = None


class ChatSession(BaseModel):
	session_id: str
	created_at: str
	messages: list[ChatMessage] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
	message: str


class SendMessageResponse(BaseModel):
	session_id: str
	user_message: ChatMessage
	assistant_message: ChatMessage
	tool_rounds: int


@app.post("/chat")
async def create_chat_session() -> ChatSession:
	session_id = uuid4().hex[:12]
	now = datetime.now(timezone.utc).isoformat()

	graph = build_async_graph(6)
	_chat_graphs[session_id] = graph
	_chat_histories[session_id] = []

	log.info("chat_session_created", session_id=session_id)
	return ChatSession(session_id=session_id, created_at=now)


@app.get("/chat/{session_id}")
async def get_chat_session(session_id: str) -> ChatSession:
	history = _chat_histories.get(session_id)
	if history is None:
		raise HTTPException(status_code=404, detail="chat session not found")
	return ChatSession(
		session_id=session_id,
		created_at=history[0]["timestamp"] if history else "",
		messages=[ChatMessage(**m) for m in history],
	)


@app.post("/chat/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest) -> SendMessageResponse:
	graph = _chat_graphs.get(session_id)
	if graph is None:
		raise HTTPException(status_code=404, detail="chat session not found")

	now = datetime.now(timezone.utc).isoformat()
	user_msg = ChatMessage(role="user", content=req.message, timestamp=now)
	_chat_histories[session_id].append(user_msg.model_dump())

	config = {"configurable": {"thread_id": session_id}}
	initial_state = {
		"messages": [HumanMessage(content=req.message)],
		"tool_rounds": 0,
		"done": False,
		"current_query": "",
		"search_plan": [],
		"raw_results": [],
		"validated_results": [],
	}

	with trace_context(run_id=session_id, name="nightout-m6-chat", module=6, input=req.message):
		try:
			result = await asyncio.wait_for(
				graph.ainvoke(initial_state, config=config),
				timeout=90,
			)
		except TimeoutError:
			result = {"messages": [AIMessage(content="Search took too long — please try a simpler query.")], "tool_rounds": 0}

	last_ai = None
	for msg in reversed(result["messages"]):
		if isinstance(msg, AIMessage) and msg.content:
			last_ai = msg
			break

	assistant_content = last_ai.content if last_ai else "I wasn't able to generate a response."
	assistant_now = datetime.now(timezone.utc).isoformat()
	assistant_msg = ChatMessage(role="assistant", content=assistant_content, timestamp=assistant_now)
	_chat_histories[session_id].append(assistant_msg.model_dump())

	log.info("chat_message", session_id=session_id, tool_rounds=result.get("tool_rounds", 0))
	return SendMessageResponse(
		session_id=session_id,
		user_message=user_msg,
		assistant_message=assistant_msg,
		tool_rounds=result.get("tool_rounds", 0),
	)
