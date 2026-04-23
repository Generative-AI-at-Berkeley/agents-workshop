import { apiGet, apiPost } from "./client";
import {
  type NightOutInput,
  type RunRecord,
  type RunResponse,
  RunRecordSchema,
  RunResponseSchema,
} from "./types";

export async function createRun(input: NightOutInput): Promise<RunRecord> {
  const raw = await apiPost<unknown>("/runs", input);
  return RunRecordSchema.parse(raw);
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<RunResponse> {
  const raw = await apiGet<unknown>(`/runs/${runId}`, signal);
  return RunResponseSchema.parse(raw);
}
