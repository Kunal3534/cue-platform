"use client";
import { create } from "zustand";
import type { Flag } from "@/lib/api/types";

interface FlagsState {
  flags: Flag[];
  drawerOpen: boolean;
  setFlags: (flags: Flag[]) => void;
  addFlag: (flag: Flag) => void;
  removeFlag: (id: string) => void;
  openDrawer: () => void;
  closeDrawer: () => void;
}

export const useFlagsStore = create<FlagsState>((set) => ({
  flags: [],
  drawerOpen: false,
  setFlags: (flags) => set({ flags }),
  addFlag: (flag) =>
    set((s) => ({
      flags: s.flags.some((f) => f.id === flag.id)
        ? s.flags
        : [flag, ...s.flags],
    })),
  removeFlag: (id) =>
    set((s) => ({ flags: s.flags.filter((f) => f.id !== id) })),
  openDrawer: () => set({ drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),
}));
