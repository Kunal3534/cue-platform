"use client";
import { useCallback } from "react";
import { useChatStore } from "@/stores/chat";
import type { ChatMessage } from "@/lib/api/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type StreamEvent =
  | { type: "assistant_delta"; text: string }
  | { type: "tool_call"; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; name: string; result: unknown }
  | { type: "preview_ready"; batch_id: string }
  | { type: "done"; message?: ChatMessage }
  | { type: "message_complete"; message?: ChatMessage };

export function useChatStream(projectId: string, threadId: string | null) {
  const {
    appendMessage,
    setStreamingText,
    appendStreamingText,
    addToolCall,
    addToolResult,
    setPendingBatchId,
    clearTurns,
  } = useChatStore();

  const send = useCallback(
    async (content: string) => {
      if (!threadId) return;

      setStreamingText("");
      clearTurns();

      const res = await fetch(
        `${API}/projects/${projectId}/chat/threads/${threadId}/messages`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        },
      );

      if (!res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";

      // Track in-flight tool turn so we can pair result to call
      let currentTurnId: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw || raw === "[DONE]") continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(raw) as StreamEvent;
          } catch {
            continue;
          }

          switch (event.type) {
            case "assistant_delta":
              accumulated += event.text;
              appendStreamingText(event.text);
              break;

            case "tool_call":
              currentTurnId = addToolCall({
                name: event.name,
                arguments: event.arguments,
              });
              break;

            case "tool_result":
              if (currentTurnId) {
                addToolResult(currentTurnId, {
                  name: event.name,
                  result: event.result,
                });
                currentTurnId = null;
              }
              break;

            case "preview_ready":
              setPendingBatchId(event.batch_id);
              break;

            case "done":
            case "message_complete": {
              const msg =
                event.message ??
                (accumulated
                  ? ({
                      id: crypto.randomUUID(),
                      thread_id: threadId,
                      role: "assistant" as const,
                      content: accumulated,
                      tool_calls: null,
                      edits_batch_id: null,
                      created_at: new Date().toISOString(),
                    } satisfies ChatMessage)
                  : null);
              if (msg) appendMessage(msg);
              setStreamingText(null);
              accumulated = "";
              break;
            }
          }
        }
      }

      setStreamingText(null);
    },
    [
      threadId,
      projectId,
      appendMessage,
      setStreamingText,
      appendStreamingText,
      addToolCall,
      addToolResult,
      setPendingBatchId,
      clearTurns,
    ],
  );

  return { send };
}
