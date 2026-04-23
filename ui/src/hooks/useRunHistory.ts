import { useEffect, useState } from "react";
import type { RunRecord } from "../api/types";

const KEY = "nightout:run-history";
const MAX = 50;

export interface HistoryEntry {
  run_id: string;
  city: string;
  vibe: string;
  created_at: string;
  status: RunRecord["status"];
}

function read(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e): e is HistoryEntry =>
        typeof e === "object" &&
        e !== null &&
        typeof (e as HistoryEntry).run_id === "string",
    );
  } catch {
    return [];
  }
}

function write(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(0, MAX)));
    window.dispatchEvent(new Event("nightout:history"));
  } catch {
    /* quota */
  }
}

export function remember(record: RunRecord) {
  const entries = read();
  const next: HistoryEntry[] = [
    {
      run_id: record.run_id,
      city: record.input.city,
      vibe: record.input.vibe,
      created_at: record.created_at,
      status: record.status,
    },
    ...entries.filter((e) => e.run_id !== record.run_id),
  ];
  write(next);
}

export function updateHistoryStatus(record: RunRecord) {
  const entries = read();
  const next = entries.map((e) =>
    e.run_id === record.run_id ? { ...e, status: record.status } : e,
  );
  write(next);
}

export function useRunHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(() => read());
  useEffect(() => {
    const handler = () => setEntries(read());
    window.addEventListener("nightout:history", handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener("nightout:history", handler);
      window.removeEventListener("storage", handler);
    };
  }, []);
  return entries;
}
