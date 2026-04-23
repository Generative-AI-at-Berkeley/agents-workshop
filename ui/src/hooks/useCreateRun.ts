import { useMutation } from "@tanstack/react-query";
import { createRun } from "../api/runs";
import type { NightOutInput, RunRecord } from "../api/types";
import { remember } from "./useRunHistory";

export function useCreateRun(onSuccess?: (record: RunRecord) => void) {
  return useMutation({
    mutationFn: (input: NightOutInput) => createRun(input),
    onSuccess: (record) => {
      remember(record);
      onSuccess?.(record);
    },
  });
}
