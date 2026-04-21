"use client";
import { useEffect } from "react";
import { useFlagsStore } from "@/stores/flags";
import { useQueryClient } from "@tanstack/react-query";
import type { Flag } from "@/lib/api/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ProjectEvent = {
  kind: string;
  flag?: Flag;
  batch_id?: string;
  views_affected?: string[];
  view?: string;
};

// EventSource does not surface reconnect attempts; it silently reconnects on
// its own. We add a manual backoff layer on top: if the connection errors, we
// close it and reopen after a delay that grows up to 30s, capped.
export function useProjectEvents(projectId: string | null) {
  const addFlag = useFlagsStore((s) => s.addFlag);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId) return;

    let es: EventSource | null = null;
    let closed = false;
    let attempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;

      es = new EventSource(`${API}/projects/${projectId}/events`, {
        withCredentials: true,
      });

      es.onopen = () => {
        attempt = 0;
      };

      es.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data) as ProjectEvent;

          if (payload.kind === "flag_raised" && payload.flag) {
            addFlag(payload.flag);
          }

          const viewInvalidate = (views: string[]) => {
            for (const view of views) {
              queryClient.invalidateQueries({
                queryKey: ["view", projectId, view],
              });
            }
          };

          if (
            payload.kind === "scene_rescheduled" ||
            payload.kind === "day_updated" ||
            payload.kind === "edit_committed"
          ) {
            viewInvalidate(payload.views_affected ?? []);
          }

          if (payload.kind === "view_regenerated" && payload.view) {
            queryClient.invalidateQueries({
              queryKey: ["view", projectId, payload.view],
            });
          }

          if (payload.kind === "call_sheet_regenerated") {
            queryClient.invalidateQueries({
              queryKey: ["callsheets", projectId],
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        // EventSource handles transient disconnects on its own, but on hard
        // failure (CONNECTING stays stuck) we force a reconnect with backoff.
        if (es?.readyState === EventSource.CLOSED) {
          attempt += 1;
          const delay = Math.min(30_000, 500 * 2 ** Math.min(attempt, 6));
          reconnectTimer = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [projectId, addFlag, queryClient]);
}
