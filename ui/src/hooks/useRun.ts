import { useQuery } from "@tanstack/react-query";
import { getRun } from "../api/runs";
import type { RunResponse } from "../api/types";

export function useRun(runId: string | null) {
  return useQuery<RunResponse>({
    queryKey: ["run", runId],
    queryFn: ({ signal }) => getRun(runId!, signal),
    enabled: runId !== null,
    refetchInterval: (q) => {
      const status = q.state.data?.record.status;
      return status === "pending" || status === "running" ? 2000 : false;
    },
  });
}
