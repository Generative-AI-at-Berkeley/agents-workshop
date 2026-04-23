import { FormEvent, useState } from "react";
import { ArrowRight, Clock, Moon } from "lucide-react";
import { motion } from "motion/react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { useCreateRun } from "../hooks/useCreateRun";
import { useRunHistory } from "../hooks/useRunHistory";
import { navigate } from "../hooks/useHashRoute";
import { formatRelativeTime } from "../lib/format";

export function HomeRoute() {
  const [city, setCity] = useState("");
  const [vibe, setVibe] = useState("");
  const [date, setDate] = useState("this saturday");
  const [groupSize, setGroupSize] = useState("4");

  const history = useRunHistory();

  const createRun = useCreateRun((record) => {
    navigate({ name: "run", runId: record.run_id });
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!city.trim() || !vibe.trim()) return;
    createRun.mutate({
      city: city.trim(),
      vibe: vibe.trim(),
      date: date.trim() || "this saturday",
      group_size: parseInt(groupSize) || 4,
      notes: "",
    });
  }

  return (
    <div className="relative flex min-h-[calc(100dvh-3rem)] flex-col">
      <div className="hero-glow pointer-events-none absolute inset-x-0 top-0 -z-20 h-[min(520px,55vh)]" />
      <div className="hero-grid pointer-events-none absolute inset-x-0 top-0 -z-10 h-[min(480px,50vh)] opacity-70 dark:opacity-100" />

      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-5 pb-16 pt-12 sm:px-6 sm:pt-20">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="space-y-4 text-center"
        >
          <Badge tone="accent" size="md" className="inline-flex">
            <Moon className="size-3" /> multi-agent nightlife planner
          </Badge>
          <h1 className="text-hero font-600 tracking-slight text-balance text-ink">
            nightout
          </h1>
          <p className="text-lg font-400 mx-auto max-w-md text-pretty text-ink-muted">
            tell us the city and the vibe. we'll plan the rest.
          </p>
        </motion.div>

        <motion.form
          onSubmit={onSubmit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.35 }}
          className="mt-10 space-y-3"
        >
          <div className="flex items-center gap-2 rounded-2xl border border-outline-200 bg-surface-raised p-1.5 shadow-sm ring-1 ring-black/[0.04] transition-[box-shadow,border-color] focus-within:border-brand-600/80 focus-within:shadow-md focus-within:ring-2 focus-within:ring-brand-500/25 dark:border-outline-200 dark:ring-white/[0.06] dark:focus-within:border-brand-600 dark:focus-within:ring-brand-500/20">
            <Input
              size="lg"
              placeholder="berlin"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="!border-0 !shadow-none focus:!ring-0"
              autoFocus
              aria-label="City"
            />
            <Button
              type="submit"
              intent="primary"
              size="lg"
              className="shrink-0 rounded-xl"
              isDisabled={!city.trim() || !vibe.trim() || createRun.isPending}
            >
              {createRun.isPending ? "Planning..." : "Plan night"}
              <ArrowRight className="size-4" />
            </Button>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <Input
                placeholder="techno, dark, underground"
                value={vibe}
                onChange={(e) => setVibe(e.target.value)}
                aria-label="Vibe"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                placeholder="this saturday"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                aria-label="Date"
              />
              <Input
                placeholder="4"
                value={groupSize}
                onChange={(e) => setGroupSize(e.target.value)}
                aria-label="Group size"
                type="number"
              />
            </div>
          </div>

          {createRun.isError ? (
            <Card padding="sm" className="border-system-red/40 bg-system-light-red">
              <p className="text-sm font-500 text-system-red">
                {(createRun.error as Error).message}
              </p>
            </Card>
          ) : null}
        </motion.form>

        {history.length > 0 ? (
          <div className="mt-16 space-y-3">
            <h2 className="text-md font-600 flex items-center gap-2 px-1 text-ink">
              <Clock className="size-4 text-ink-muted" />
              Recent plans
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {history.slice(0, 4).map((entry) => (
                <Card
                  key={entry.run_id}
                  padding="md"
                  hoverable
                  onClick={() => navigate({ name: "run", runId: entry.run_id })}
                >
                  <div className="text-md font-500 truncate text-ink">
                    {entry.city}
                  </div>
                  <div className="text-sm text-ink-muted truncate">{entry.vibe}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <StatusBadge status={entry.status} />
                    <span className="text-xs font-500 text-ink-muted">
                      {formatRelativeTime(entry.created_at)}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: "pending" | "running" | "completed" | "failed";
}) {
  if (status === "completed") return <Badge tone="success">done</Badge>;
  if (status === "failed") return <Badge tone="danger">failed</Badge>;
  if (status === "running") return <Badge tone="accent">planning...</Badge>;
  return <Badge tone="neutral">pending</Badge>;
}
