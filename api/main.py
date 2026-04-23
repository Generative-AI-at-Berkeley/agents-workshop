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
from pydantic import BaseModel

from graph.registry import build_async_graph, initial_state
from observability import trace_context
from schemas.nightout import Itinerary, NightOutRequest

log = structlog.get_logger(__name__)

app = FastAPI(title="agents-workshop", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

_runs: dict[str, RunRecord] = {}
_results: dict[str, Itinerary] = {}


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
