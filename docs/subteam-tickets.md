# Apple SP26 — Subteam Tickets

Due: Saturday Apr 26 (individual work). Saturday worksession for cross-team integration.

---

## Skills & Prompts Team

### SP-01: Define the Global Manifest YAML schema
**When:** Wed Apr 23

Design the validation rules config format. Each rule specifies: `signal` (blur, exposure, etc.), `model_id` (HuggingFace model ref), `threshold` (numeric), `operator` (gt/lt/eq). This is the contract between all three teams — the manifest drives what the supervisor decomposes and what the workers execute.

Deliverable: `config/manifest_schema.py` (Pydantic model) + `config/manifest.example.yaml` with 3-4 sample rules.

### SP-02: Write the supervisor agent prompt
**When:** Wed Apr 23 – Thu Apr 24

The supervisor reads the manifest and decomposes it into per-image validation tasks. It outputs structured JSON assignments (like M5's manager pattern): which worker gets which image + which rules to apply.

Deliverable: `agents/supervisor.md`

### SP-03: Write worker agent prompts
**When:** Thu Apr 24

One prompt per validation signal type. Each worker receives an image + rule, calls the inference tool, interprets the result, and returns a tri-state decision: APPROVED / REJECTED / RETRY with reasoning.

Deliverable: `agents/blur_worker.md`, `agents/exposure_worker.md`, etc. (one per signal in the example manifest)

### SP-04: Write the reviewer agent prompt
**When:** Thu Apr 24 – Fri Apr 25

The reviewer checks merged results after all workers complete. It ensures no images are stuck in RETRY, flags inconsistencies, and produces the final audit summary.

Deliverable: `agents/reviewer.md`

### SP-05: Prompt iteration with dummy outputs
**When:** Fri Apr 25

Test all prompts against mocked inference outputs. Verify the supervisor decomposes correctly, workers produce valid tri-state JSON, and the reviewer catches RETRY states. No real models needed — use hardcoded tool responses.

Deliverable: Manual test log showing each prompt works with mock data.

---

## HuggingFace & ML Team

### ML-01: Research and select models for each signal
**When:** Wed Apr 23

Pick a HuggingFace model for each validation signal in the example manifest (blur detection, exposure analysis, etc.). Criteria: runs on CPU or free-tier GPU, inference under 5s per image, publicly available weights.

Deliverable: Table of signal → model_id → model card link → expected input/output format.

### ML-02: Write the blur detection inference wrapper
**When:** Wed Apr 23 – Thu Apr 24

Stateless async function: takes an image path/URL + threshold + operator, runs the model, returns `{score: float, pass: bool}`. Follow the same pattern as `tools/` in agents-workshop — pure function, no LLM logic.

Deliverable: `tools/blur_detector.py` with a `run()` method matching the tool interface.

### ML-03: Write the exposure detection inference wrapper
**When:** Thu Apr 24

Same pattern as ML-02 but for exposure/brightness analysis.

Deliverable: `tools/exposure_detector.py`

### ML-04: Write wrappers for remaining signals
**When:** Thu Apr 24 – Fri Apr 25

One wrapper per additional signal in the manifest. Each follows the same interface: image in, score + pass/fail out.

Deliverable: One `tools/<signal>_detector.py` per signal.

### ML-05: Benchmark all models
**When:** Fri Apr 25

Run each wrapper against 10-20 test images. Measure: accuracy (does it catch known-bad images?), latency (p50/p95), and memory usage. Flag any model that's too slow or inaccurate for swap-out on Saturday.

Deliverable: `docs/model-benchmarks.md` — table of signal × accuracy × p50 latency.

---

## Saturday Worksession Agenda

All three teams converge. Bring your deliverables.

1. **Manifest contract review** — SP-01 schema + ML-01 model table. Lock the signal list.
2. **Wire prompts to tools** — SP prompts call ML inference wrappers. Verify the interface matches.
3. **Agent pipeline walkthrough** — Agent team demos the LangGraph workflow with real prompts and real tools.
4. **E2E integration test** — Run one image through the full pipeline: manifest → supervisor → workers → merge → reviewer.
5. **Fix what breaks** — Expect interface mismatches. Fix them live.
