"use client";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  listScenarios,
  forkScenario,
  deleteScenario,
  mergeScenario,
} from "@/lib/api";
import { useProjectStore } from "@/stores/project";

export default function ScenariosPage() {
  const params = useParams();
  const projectId = params.id as string;
  const qc = useQueryClient();
  const { activeScenarioId, setScenario } = useProjectStore();
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: scenarios, isLoading, error: loadError } = useQuery({
    queryKey: ["scenarios", projectId],
    queryFn: () => listScenarios(projectId),
    retry: false,
  });

  const fork = useMutation({
    mutationFn: (name: string) => forkScenario(projectId, name),
    onSuccess: () => {
      setNewName("");
      setError(null);
      qc.invalidateQueries({ queryKey: ["scenarios", projectId] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Fork failed"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteScenario(projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenarios", projectId] }),
    onError: (e) => setError(e instanceof Error ? e.message : "Delete failed"),
  });

  const merge = useMutation({
    mutationFn: (id: string) => mergeScenario(projectId, id),
    onSuccess: () => {
      setScenario(null);
      qc.invalidateQueries();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Merge failed"),
  });

  if (isLoading) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading scenarios…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="row" style={{ marginBottom: "32px" }}>
        <div>
          <div className="meta meta--red" style={{ marginBottom: "4px" }}>Scenarios</div>
          <p className="voice" style={{ fontSize: "15px" }}>
            Fork the schedule to explore alternatives without touching live data.
          </p>
        </div>
      </div>

      {loadError && (
        <div
          className="mono-xs"
          style={{
            color: "var(--cue-red)",
            background: "var(--cue-red-10)",
            padding: "10px 14px",
            border: "1px solid var(--cue-red)",
            marginBottom: "24px",
          }}
        >
          Failed to load scenarios: {loadError instanceof Error ? loadError.message : String(loadError)}
        </div>
      )}
      {error && (
        <div className="mono-xs" style={{ color: "var(--cue-red)", marginBottom: "12px" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: "12px", marginBottom: "32px" }}>
        <div className="chat-input" style={{ flex: 1 }}>
          <input
            type="text"
            placeholder="Scenario name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newName.trim()) fork.mutate(newName.trim());
            }}
          />
        </div>
        <button
          className="btn btn--primary"
          disabled={!newName.trim() || fork.isPending}
          onClick={() => fork.mutate(newName.trim())}
        >
          Fork →
        </button>
      </div>

      <div className="projects" style={{ borderTop: "var(--rule)" }}>
        <div
          className="project-row"
          style={{ cursor: "pointer" }}
          onClick={() => setScenario(null)}
        >
          <span
            className="project-row__chip"
            style={{ background: activeScenarioId === null ? "var(--cue-red)" : "var(--day)" }}
          >
            L
          </span>
          <div>
            <div className="project-row__title">Live Schedule</div>
            <div className="project-row__sub">The canonical production schedule</div>
          </div>
          <div />
          <span
            className="project-row__open"
            style={{ color: activeScenarioId === null ? "var(--cue-red)" : undefined }}
          >
            {activeScenarioId === null ? "Active" : "Switch"}
          </span>
        </div>

        {(scenarios ?? []).map((sc) => (
          <div key={sc.id} className="project-row" style={{ cursor: "default" }}>
            <span
              className="project-row__chip"
              style={{ background: activeScenarioId === sc.id ? "var(--cue-red)" : "var(--day-int)" }}
              onClick={() => setScenario(sc.id)}
            >
              {sc.name[0]?.toUpperCase()}
            </span>
            <div onClick={() => setScenario(sc.id)} style={{ cursor: "pointer" }}>
              <div className="project-row__title">{sc.name}</div>
              <div className="project-row__sub">
                Forked {new Date(sc.created_at).toLocaleDateString("en-IN")}
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn btn--sm btn--day"
                onClick={() => setScenario(sc.id)}
                disabled={activeScenarioId === sc.id}
              >
                {activeScenarioId === sc.id ? "Viewing" : "View"}
              </button>
              <button
                className="btn btn--sm btn--primary"
                onClick={() => {
                  if (window.confirm(`Merge "${sc.name}" into Live?`)) {
                    merge.mutate(sc.id);
                  }
                }}
                disabled={merge.isPending}
              >
                Merge → Live
              </button>
              <button
                className="btn btn--sm btn--ghost"
                onClick={() => {
                  if (window.confirm(`Delete scenario "${sc.name}"?`)) {
                    remove.mutate(sc.id);
                  }
                }}
                disabled={remove.isPending}
              >
                Delete
              </button>
            </div>
            <span
              className="project-row__open"
              style={{ color: activeScenarioId === sc.id ? "var(--cue-red)" : undefined }}
            >
              {activeScenarioId === sc.id ? "Active" : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
