"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getTodos, saveTodos } from "@/lib/api";
import type { TodoItem } from "@/lib/api/types";

/**
 * Producer-only to-dos for one shoot day. All days' items live in one list
 * on the project; this component shows and edits only this day's slice.
 * Never rendered on the share page, and the data never enters the share
 * payload.
 */
export default function DayTodos({
  projectId,
  date,
}: {
  projectId: string;
  date: string;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [saveError, setSaveError] = useState(false);

  const { data } = useQuery({
    queryKey: ["todos", projectId],
    queryFn: () => getTodos(projectId),
  });

  if (!data) return null;

  const dayTodos = data.todos.filter((t) => t.date === date);

  // Rebase every save on a fresh fetch so a stale cache can't overwrite
  // the other producer's items.
  const persist = async (update: (fresh: TodoItem[]) => TodoItem[]) => {
    setSaveError(false);
    try {
      const fresh = await qc.fetchQuery({
        queryKey: ["todos", projectId],
        queryFn: () => getTodos(projectId),
        staleTime: 0,
      });
      await saveTodos(projectId, update(fresh.todos));
      await qc.invalidateQueries({ queryKey: ["todos", projectId] });
    } catch {
      setSaveError(true);
    }
  };

  const addTodo = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    void persist((fresh) => [...fresh, { id: crypto.randomUUID(), text, done: false, date }]);
  };

  return (
    <div style={{ marginTop: 44 }}>
      <div className="gq-moodboard__head">
        <span>To-do</span>
        <span style={{ color: "var(--g-muted)", textTransform: "none", letterSpacing: "0.04em" }}>
          only you see this — not on the share link
        </span>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
        <input
          className="gq-input"
          value={draft}
          placeholder="Add an item for this day — confirm call time, chase manager…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTodo()}
        />
        <button type="button" className="gq-btn" onClick={addTodo} style={{ flex: "none" }}>
          Add
        </button>
      </div>

      <div style={{ marginTop: 6 }}>
        {dayTodos.map((t) => (
          <div key={t.id} className="gq-todo">
            <input
              type="checkbox"
              className="gq-check"
              checked={t.done}
              onChange={() =>
                void persist((fresh) =>
                  fresh.map((x) => (x.id === t.id ? { ...x, done: !x.done } : x)),
                )
              }
            />
            <span className={`gq-todo__text${t.done ? " is-done" : ""}`}>{t.text}</span>
            <button
              type="button"
              className="gq-todo__del"
              aria-label="Delete"
              onClick={() => void persist((fresh) => fresh.filter((x) => x.id !== t.id))}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {saveError && (
        <p style={{ color: "#C33", fontSize: 12, marginTop: 10 }}>
          Could not save — check the connection and try again.
        </p>
      )}
    </div>
  );
}
