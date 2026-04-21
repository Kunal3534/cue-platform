"use client";
import { create } from "zustand";
import type { ProjectDetail } from "@/lib/api/types";

interface ProjectState {
  project: ProjectDetail | null;
  activeScenarioId: string | null;
  setProject: (p: ProjectDetail) => void;
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
