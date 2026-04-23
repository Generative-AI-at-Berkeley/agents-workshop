import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "run"; runId: string };

function parse(): Route {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash.startsWith("/runs/")) {
    const runId = hash.slice("/runs/".length);
    if (runId) return { name: "run", runId };
  }
  return { name: "home" };
}

export function useHashRoute(): [Route, (r: Route) => void] {
  const [route, setRoute] = useState<Route>(() => parse());
  useEffect(() => {
    const handler = () => setRoute(parse());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return [
    route,
    (r: Route) => {
      navigate(r);
    },
  ];
}

export function navigate(r: Route) {
  const hash = r.name === "home" ? "" : `/runs/${r.runId}`;
  window.location.hash = hash;
}
