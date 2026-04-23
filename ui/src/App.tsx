import { Component, type ReactNode } from "react";
import { useHashRoute } from "./hooks/useHashRoute";
import { Header } from "./components/presentation/Header";
import { HomeRoute } from "./routes/home";
import { RunRoute } from "./routes/run";

export function App() {
  const [route] = useHashRoute();
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <ErrorBoundary>
          {route.name === "home" ? <HomeRoute /> : null}
          {route.name === "run" ? <RunRoute runId={route.runId} /> : null}
        </ErrorBoundary>
      </main>
    </div>
  );
}

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error) {
    console.error("UI error:", error);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-xl px-6 py-16 text-center">
          <h1 className="text-h-md font-600 mb-2 text-ink">Something broke</h1>
          <pre className="text-sm overflow-auto rounded-md bg-dark-50 p-3 text-left font-mono text-ink-muted dark:bg-dark-900">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => {
              this.setState({ error: null });
              window.location.hash = "";
            }}
            className="text-sm font-500 mt-4 text-brand-700 hover:underline"
          >
            Return home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
