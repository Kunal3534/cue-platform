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

export function useProjectEvents(projectId: string | null) {
  const addFlag = useFlagsStore((s) => s.addFlag);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId) return;

    const es = new EventSource(`${API}/projects/${projectId}/events`, {
      withCredentials: true,
    });

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data) as ProjectEvent;

        // Flag raised — push to flags store
        if (payload.kind === "flag_raised" && payload.flag) {
          addFlag(payload.flag);
        }

        // View-level invalidation (multiple views in one event)
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

        // view_regenerated fires once per view with the new payload
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

    return () => es.close();
  }, [projectId, addFlag, queryClient]);
}
