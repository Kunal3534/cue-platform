"use client";
import { create } from "zustand";
import type { ProjectSummary } from "@/lib/api/types";

interface ProjectState {
  project: ProjectSummary | null;
  activeScenarioId: string | null;
  setProject: (p: ProjectSummary) => void;
  setScenario: (id: string | null) => void;
  clear: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  project: null,
  activeScenarioId: null,
  setProject: (project) => set({ project }),
  setScenario: (activeScenarioId) => set({ activeScenarioId }),
  clear: () => set({ project: null, activeScenarioId: null }),
}));
