import { Moon } from "lucide-react";
import { navigate } from "../../hooks/useHashRoute";

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-outline-100 bg-surface/75 backdrop-blur-xl dark:border-outline-100/80 dark:bg-surface/70">
      <div className="mx-auto flex h-12 w-full max-w-6xl items-center justify-between px-5 sm:px-6">
        <button
          type="button"
          onClick={() => navigate({ name: "home" })}
          className="group flex items-center gap-2.5 rounded-lg outline-none ring-offset-2 ring-offset-surface focus-visible:ring-2 focus-visible:ring-brand-600"
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand-500 text-brand-foreground shadow-[0_0_0_1px_rgba(0,0,0,0.06)] dark:shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
            <Moon className="size-4" />
          </span>
          <span className="text-lg font-600 tracking-slight text-ink">nightout</span>
          <span className="text-sm font-500 hidden text-ink-muted sm:inline">
            agents workshop
          </span>
        </button>
      </div>
    </header>
  );
}
