"use client";
import { create } from "zustand";
import type { ChatMessage } from "@/lib/api/types";

export interface ToolCallEvent {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultEvent {
  name: string;
  result: unknown;
}

export interface ChatTurn {
  id: string;
  toolCall?: ToolCallEvent;
  toolResult?: ToolResultEvent;
}

interface ChatState {
  threads: import("@/lib/api/types").ChatThread[];
  activeThreadId: string | null;
  messages: ChatMessage[];
  streamingText: string | null;
  turns: ChatTurn[];             // in-flight tool events for current stream
  pendingBatchId: string | null; // from preview_ready event
  setThreads: (threads: import("@/lib/api/types").ChatThread[]) => void;
  addThread: (thread: import("@/lib/api/types").ChatThread) => void;
  setActiveThread: (id: string) => void;
  setMessages: (messages: ChatMessage[]) => void;
  appendMessage: (msg: ChatMessage) => void;
  setStreamingText: (text: string | null) => void;
  appendStreamingText: (delta: string) => void;
  addToolCall: (call: ToolCallEvent) => string;
  addToolResult: (turnId: string, result: ToolResultEvent) => void;
  setPendingBatchId: (id: string | null) => void;
  clearTurns: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  threads: [],
  activeThreadId: null,
  messages: [],
  streamingText: null,
  turns: [],
  pendingBatchId: null,

  setThreads: (threads) => set({ threads }),
  addThread: (thread) => set((s) => ({ threads: [thread, ...s.threads] })),
  setActiveThread: (activeThreadId) => set({ activeThreadId }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setStreamingText: (streamingText) => set({ streamingText }),
  appendStreamingText: (delta) =>
    set((s) => ({ streamingText: (s.streamingText ?? "") + delta })),

  addToolCall: (call) => {
    const id = crypto.randomUUID();
    set((s) => ({ turns: [...s.turns, { id, toolCall: call }] }));
    return id;
  },

  addToolResult: (turnId, result) =>
    set((s) => ({
      turns: s.turns.map((t) =>
        t.id === turnId ? { ...t, toolResult: result } : t,
      ),
    })),

  setPendingBatchId: (pendingBatchId) => set({ pendingBatchId }),
  clearTurns: () => set({ turns: [], pendingBatchId: null }),
}));
