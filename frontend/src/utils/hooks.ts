import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { ApplicationStatus, LifecycleMeta } from "../api/types";

/** Call `callback` every `intervalMs` while the tab is visible; null pauses polling. */
export function usePolling(callback: () => void | Promise<void>, intervalMs: number | null): void {
  const saved = useRef(callback);

  useEffect(() => {
    saved.current = callback;
  }, [callback]);

  useEffect(() => {
    if (intervalMs === null) return undefined;
    const tick = () => {
      if (!document.hidden) void saved.current();
    };
    const timer = window.setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [intervalMs]);
}

let lifecycleRequest: Promise<LifecycleMeta> | null = null;

/** Status labels straight from the backend state model (GET /api/meta/lifecycle). */
export function useStatusLabels(): Partial<Record<ApplicationStatus, string>> {
  const [labels, setLabels] = useState<Partial<Record<ApplicationStatus, string>>>({});

  useEffect(() => {
    let active = true;
    lifecycleRequest ??= api.lifecycle();
    lifecycleRequest
      .then((meta) => {
        if (active) setLabels(Object.fromEntries(meta.statuses.map((s) => [s.status, s.label])));
      })
      .catch(() => {
        lifecycleRequest = null; // retry on the next mount
      });
    return () => {
      active = false;
    };
  }, []);

  return labels;
}
