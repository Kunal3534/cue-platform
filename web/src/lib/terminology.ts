"use client";
import { useProjectStore } from "@/stores/project";

/**
 * Editorial projects (settings.mode === "editorial") speak magazine, not film:
 * scenes are segments, cast is talent, the calendar is the product.
 * The data model is unchanged — this is purely a label layer.
 */
export interface Terms {
  mode: "film" | "editorial";
  scene: string;
  scenes: string;
  cast: string;
  shootDays: string;
  unscheduled: string;
}

const FILM: Terms = {
  mode: "film",
  scene: "Scene",
  scenes: "Scenes",
  cast: "Cast",
  shootDays: "shoot days",
  unscheduled: "Unscheduled",
};

const EDITORIAL: Terms = {
  mode: "editorial",
  scene: "Segment",
  scenes: "Segments",
  cast: "Talent",
  shootDays: "shoot days",
  unscheduled: "Unplaced segments",
};

export function useTerms(): Terms {
  const project = useProjectStore((s) => s.project);
  return project?.settings?.mode === "editorial" ? EDITORIAL : FILM;
}

export function useIsEditorial(): boolean {
  const project = useProjectStore((s) => s.project);
  return project?.settings?.mode === "editorial";
}
