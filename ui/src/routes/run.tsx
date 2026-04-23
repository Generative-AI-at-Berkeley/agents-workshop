import { useEffect } from "react";
import { ArrowLeft, MapPin, Clock as ClockIcon, Flame, ExternalLink } from "lucide-react";
import { motion } from "motion/react";
import { useRun } from "../hooks/useRun";
import { updateHistoryStatus } from "../hooks/useRunHistory";
import { navigate } from "../hooks/useHashRoute";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Spinner, ThinkingBar } from "../components/ui/Spinner";
import { formatDuration } from "../lib/format";
import type { Stop } from "../api/types";

const LANGFUSE_BASE = "http://localhost:3200";

export function RunRoute({ runId }: { runId: string }) {
  const { data, isLoading, error } = useRun(runId);

  useEffect(() => {
    if (data?.record) {
      updateHistoryStatus(data.record);
    }
  }, [data?.record]);

  if (isLoading || !data) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-4xl items-center justify-center px-6">
        <div className="flex flex-col items-center gap-3 text-ink-muted">
          <Spinner className="!text-3xl" />
          <span className="text-sm font-500">Planning your night...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-12">
        <Card padding="md" className="border-system-red/40 bg-system-light-red">
          <p className="text-md font-500 text-system-red">{(error as Error).message}</p>
        </Card>
      </div>
    );
  }

  const { record, itinerary } = data;
  const isRunning = record.status === "running" || record.status === "pending";

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Button
          intent="ghost"
          size="sm"
          onPress={() => navigate({ name: "home" })}
        >
          <ArrowLeft className="size-4" />
          New plan
        </Button>
        <a
          href={`${LANGFUSE_BASE}/project/workshop/traces/${runId}`}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-500 inline-flex items-center gap-1 rounded-md px-2 py-1 text-ink-muted hover:bg-dark-100 hover:text-ink dark:hover:bg-dark-900"
        >
          Langfuse
          <ExternalLink className="size-3" />
        </a>
      </div>

      <motion.header
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="mb-8"
      >
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-h-lg font-600 tracking-slight text-ink">
            {record.input.city}
          </h1>
          <StatusBadge status={record.status} />
        </div>
        <p className="text-md text-ink-muted mt-1">{record.input.vibe}</p>
        <div className="text-sm font-500 mt-1.5 flex flex-wrap items-center gap-3 text-ink-muted">
          <span>{record.input.date} &middot; {record.input.group_size} people</span>
          <span className="tabular-nums">
            &middot; {formatDuration(record.created_at, record.completed_at ?? null)}
          </span>
        </div>
        {record.error ? (
          <Card padding="sm" className="mt-3 border-system-red/40 bg-system-light-red">
            <p className="text-sm font-500 text-system-red">{record.error}</p>
          </Card>
        ) : null}
      </motion.header>

      {isRunning ? (
        <div className="space-y-4">
          <ThinkingBar />
          <p className="text-sm text-ink-muted text-center">The agent is scouting venues...</p>
        </div>
      ) : null}

      {itinerary && itinerary.stops.length > 0 ? (
        <section className="space-y-6">
          <div className="relative space-y-0">
            {/* Timeline line */}
            <div className="absolute left-[19px] top-3 bottom-3 w-px bg-outline-200 dark:bg-outline-100" />

            {itinerary.stops.map((stop, i) => (
              <StopCard key={i} stop={stop} index={i} total={itinerary.stops.length} />
            ))}
          </div>

          {itinerary.total_estimated_cost ? (
            <Card padding="md" className="mt-6">
              <div className="flex items-center justify-between">
                <span className="text-sm font-600 text-ink">Estimated total per person</span>
                <span className="text-md font-600 text-ink">{itinerary.total_estimated_cost}</span>
              </div>
            </Card>
          ) : null}

          {itinerary.survival_tips ? (
            <Card padding="md" className="border-brand-500/20 bg-brand-200/10 dark:bg-brand-900/10">
              <div className="text-sm font-600 text-brand-700 dark:text-brand-200 mb-1">Survival tips</div>
              <p className="text-sm text-ink-muted">{itinerary.survival_tips}</p>
            </Card>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function StopCard({ stop, index, total }: { stop: Stop; index: number; total: number }) {
  const degenColor =
    stop.degen_score >= 8
      ? "danger"
      : stop.degen_score >= 5
        ? "warning"
        : "neutral";

  const categoryIcon: Record<string, string> = {
    club: "🪩",
    rave: "🔊",
    afterhours: "🌅",
    food: "🍕",
    pregame: "🍸",
    bar: "🍺",
    other: "📍",
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08, duration: 0.3 }}
      className="relative flex gap-4 pb-6"
    >
      {/* Timeline dot */}
      <div className="relative z-10 flex flex-col items-center">
        <div className={`flex size-10 items-center justify-center rounded-full border-2 text-lg ${
          index === 0
            ? "border-brand-500 bg-brand-500/10"
            : index === total - 1
              ? "border-system-green bg-system-green/10"
              : "border-outline-200 bg-surface-raised dark:border-outline-100"
        }`}>
          {categoryIcon[stop.category] ?? "📍"}
        </div>
      </div>

      <Card padding="md" hoverable={false} className="flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-600 text-brand-600 dark:text-brand-200 tabular-nums">
                <ClockIcon className="size-3 inline mr-0.5" />
                {stop.time}
              </span>
              <Badge tone="neutral" size="sm">{stop.category}</Badge>
            </div>
            <h3 className="text-md font-600 text-ink mt-1">{stop.name}</h3>
            <p className="text-sm text-ink-muted mt-0.5">{stop.vibe}</p>
          </div>
          <Badge tone={degenColor} size="md" className="shrink-0">
            <Flame className="size-3" />
            {stop.degen_score}/10
          </Badge>
        </div>

        {(stop.address || stop.cost || stop.tips) ? (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-subtle">
            {stop.address ? (
              <span className="flex items-center gap-1">
                <MapPin className="size-3" /> {stop.address}
              </span>
            ) : null}
            {stop.cost ? <span>{stop.cost}</span> : null}
          </div>
        ) : null}

        {stop.tips ? (
          <p className="mt-2 text-xs text-ink-muted italic">{stop.tips}</p>
        ) : null}
      </Card>
    </motion.div>
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
