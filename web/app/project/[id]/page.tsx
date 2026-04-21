"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listThreads, createThread, getThread } from "@/lib/api";
import { useChatStore } from "@/stores/chat";
import { useProjectStore } from "@/stores/project";
import { useChatStream } from "@/lib/sse/useChatStream";
import PreviewModal from "@/components/preview-modal/PreviewModal";

const SUGGESTIONS = [
  "What is this project?",
  "Show me shoot days with the most cast",
  "Are there any scheduling conflicts?",
  "Which scenes are still unscheduled?",
];

const TOOL_LABELS: Record<string, string> = {
  get_project_overview: "Get project overview",
  get_main_schedule: "Load main schedule",
  get_flags: "Check flags",
  propose_reschedule: "Propose reschedule",
  propose_edit: "Propose edit",
  search_scenes: "Search scenes",
  get_cast_dood: "Load cast DOOD",
  get_day_detail: "Get day detail",
};

function ToolCard({
  name,
  args,
  result,
}: {
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
}) {
  const [expanded, setExpanded] = useState(false);
  const label = TOOL_LABELS[name] ?? name;

  return (
    <div
      style={{
        border: "1px solid var(--slate)",
        background: "var(--paper)",
        padding: "10px 14px",
        marginTop: "10px",
        fontSize: "12px",
      }}
    >
      <button
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          width: "100%",
          textAlign: "left",
          background: "none",
          border: "none",
          cursor: "pointer",
          fontFamily: "var(--strip)",
          fontWeight: 700,
          fontSize: "11px",
          letterSpacing: "0.14em",
          color: "var(--slate-70)",
          textTransform: "uppercase",
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <span style={{ color: result ? "var(--slate-50)" : "var(--cue-red)" }}>
          {result ? "✓" : "⋯"}
        </span>
        {label}
        <span style={{ marginLeft: "auto", fontSize: "10px" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded && (
        <div style={{ marginTop: "8px" }}>
          {Object.keys(args).length > 0 && (
            <pre
              style={{
                fontFamily: "var(--mono)",
                fontSize: "11px",
                color: "var(--slate-70)",
                margin: "0 0 6px",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
              }}
            >
              {JSON.stringify(args, null, 2)}
            </pre>
          )}
          {result !== undefined && (
            <pre
              style={{
                fontFamily: "var(--mono)",
                fontSize: "11px",
                color: "var(--slate)",
                margin: 0,
                background: "var(--chalk)",
                padding: "6px 8px",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                maxHeight: "200px",
                overflowY: "auto",
              }}
            >
              {typeof result === "string"
                ? result
                : JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  const params = useParams();
  const projectId = params.id as string;
  const qc = useQueryClient();
  const project = useProjectStore((s) => s.project);

  const {
    threads,
    activeThreadId,
    messages,
    streamingText,
    turns,
    pendingBatchId,
    setThreads,
    addThread,
    setActiveThread,
    setMessages,
    appendMessage,
    setPendingBatchId,
  } = useChatStore();

  const [input, setInput] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const { send } = useChatStream(projectId, activeThreadId);

  const { data: threadList } = useQuery({
    queryKey: ["threads", projectId],
    queryFn: () => listThreads(projectId),
  });

  useEffect(() => {
    if (threadList) {
      setThreads(threadList);
      if (!activeThreadId && threadList.length > 0) {
        setActiveThread(threadList[0].id);
      }
    }
  }, [threadList, activeThreadId, setThreads, setActiveThread]);

  const { data: threadMessages } = useQuery({
    queryKey: ["thread-messages", projectId, activeThreadId],
    queryFn: () => getThread(projectId, activeThreadId!),
    enabled: !!activeThreadId,
  });

  useEffect(() => {
    if (threadMessages) setMessages(threadMessages);
  }, [threadMessages, setMessages]);

  useEffect(() => {
    logRef.current?.scrollTo({
      top: logRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streamingText, turns]);

  const newThread = useMutation({
    mutationFn: () => createThread(projectId),
    onSuccess: (thread) => {
      addThread(thread);
      setActiveThread(thread.id);
      setMessages([]);
      qc.invalidateQueries({ queryKey: ["threads", projectId] });
    },
  });

  const handleSend = async () => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput("");

    let tid = activeThreadId;
    if (!tid) {
      const thread = await createThread(projectId);
      addThread(thread);
      setActiveThread(thread.id);
      tid = thread.id;
    }

    appendMessage({
      id: crypto.randomUUID(),
      thread_id: tid,
      role: "user",
      content: text,
      tool_calls: null,
      edits_batch_id: null,
      created_at: new Date().toISOString(),
    });

    await send(text);
  };

  return (
    <div className="chat-shell">
      <div className="chat-main">
        <div className="chat-log" ref={logRef}>
          {messages.length === 0 && !streamingText && turns.length === 0 && (
            <div style={{ paddingTop: "24px" }}>
              <p
                className="voice"
                style={{ fontSize: "16px", color: "var(--slate-50)" }}
              >
                Ask anything about the schedule.
              </p>
              <div className="chat-suggest" style={{ marginTop: "24px" }}>
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="chat-chip"
                    onClick={() => setInput(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => {
            const body = msg.content ?? "";
            if (!body && (!msg.tool_calls || msg.tool_calls.length === 0)) {
              return null;
            }
            return (
              <div
                key={msg.id}
                className={`chat-msg${msg.role === "user" ? " chat-msg--you" : ""}`}
              >
                <div
                  className={`chat-msg__avatar${msg.role === "user" ? " chat-msg__avatar--you" : ""}`}
                >
                  {msg.role === "user" ? "Y" : "C"}
                </div>
                <div>
                  <div className="chat-msg__who">
                    {msg.role === "user" ? "You" : "Cue"}
                  </div>
                  {body && (
                    <div className="chat-msg__body">
                      <p>{body}</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* In-flight tool calls (current stream) */}
          {turns.length > 0 && (
            <div className="chat-msg">
              <div className="chat-msg__avatar">C</div>
              <div style={{ width: "100%" }}>
                <div className="chat-msg__who">Cue</div>
                {turns.map((turn) =>
                  turn.toolCall ? (
                    <ToolCard
                      key={turn.id}
                      name={turn.toolCall.name}
                      args={turn.toolCall.arguments}
                      result={turn.toolResult?.result}
                    />
                  ) : null,
                )}
              </div>
            </div>
          )}

          {/* Streaming text delta */}
          {streamingText !== null && (
            <div className="chat-msg">
              <div className="chat-msg__avatar">C</div>
              <div>
                <div className="chat-msg__who">Cue</div>
                <div className="chat-msg__body">
                  <p>
                    {streamingText}
                    <span style={{ opacity: 0.4 }}>▌</span>
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Preview ready button */}
          {pendingBatchId && (
            <div style={{ paddingTop: "16px" }}>
              <button
                className="btn btn--day"
                onClick={() => setShowPreview(true)}
              >
                Preview changes →
              </button>
            </div>
          )}
        </div>

        <div className="chat-input-wrap">
          <div className="chat-input">
            <input
              type="text"
              placeholder="Ask about the schedule…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={streamingText !== null}
            />
            <button
              className="btn btn--primary btn--sm"
              onClick={handleSend}
              disabled={!input.trim() || streamingText !== null}
            >
              Send →
            </button>
          </div>
        </div>
      </div>

      <aside className="chat-context">
        <div className="chat-context__sec">
          <div className="chat-context__lbl">Project</div>
          <div className="chat-context__val">{project?.title ?? "—"}</div>
          <div className="chat-context__val-mono">{project?.window ?? ""}</div>
        </div>
        <div className="chat-context__sec">
          <div className="chat-context__lbl">Schedule</div>
          <div className="chat-context__val">
            {project?.shoot_days ?? "—"} shoot days
          </div>
          <div className="chat-context__val-mono">
            {project?.total_days ?? "—"} total days
          </div>
        </div>
        <div className="chat-context__sec">
          <div className="chat-context__lbl">Threads</div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "6px",
              marginTop: "8px",
            }}
          >
            <button
              className="btn btn--sm btn--ghost"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={() => newThread.mutate()}
            >
              + New thread
            </button>
            {threads.slice(0, 5).map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setActiveThread(t.id);
                  qc.invalidateQueries({
                    queryKey: ["thread-messages", projectId, t.id],
                  });
                }}
                style={{
                  fontFamily: "var(--serif)",
                  fontSize: "13px",
                  textAlign: "left",
                  padding: "6px 8px",
                  background:
                    t.id === activeThreadId ? "var(--day)" : "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--slate)",
                  borderRadius: "2px",
                }}
              >
                {t.title ?? "Untitled thread"}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {showPreview && pendingBatchId && (
        <PreviewModal
          projectId={projectId}
          preview={{
            batch_id: pendingBatchId,
            diff: { views_affected: [], breaks: [], side_effects: [], flags_raised: [] },
            expires_at: new Date(Date.now() + 600_000).toISOString(),
          }}
          onClose={() => setShowPreview(false)}
          onCommitted={() => {
            setShowPreview(false);
            setPendingBatchId(null);
          }}
        />
      )}
    </div>
  );
}
