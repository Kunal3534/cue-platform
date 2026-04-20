"use client";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { listScenarios, forkScenario, deleteScenario, activateScenario } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

export default function ScenariosPage() {
  const params = useParams();
  const projectId = params.id as string;
  const qc = useQueryClient();
  const { activeScenarioId, setScenario } = useProjectStore();
  const [newName, setNewName] = useState("");

  const { data: scenarios, isLoading } = useQuery({
    queryKey: ["scenarios", projectId],
    queryFn: () => listScenarios(projectId),
  });

  const fork = useMutation({
    mutationFn: (name: string) => forkScenario(projectId, name),
    onSuccess: () => {
      setNewName("");
      qc.invalidateQueries({ queryKey: ["scenarios", projectId] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteScenario(projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenarios", projectId] }),
  });

  const activate = useMutation({
    mutationFn: (id: string) => activateScenario(projectId, id),
    onSuccess: (_, id) => {
      setScenario(id);
      qc.invalidateQueries({ queryKey: ["scenarios", projectId] });
    },
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
          style={{ cursor: "default" }}
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

        {scenarios?.map((sc) => (
          <div key={sc.id} className="project-row" style={{ cursor: "default" }}>
            <span
              className="project-row__chip"
              style={{ background: activeScenarioId === sc.id ? "var(--cue-red)" : "var(--day-int)" }}
            >
              {sc.name[0]?.toUpperCase()}
            </span>
            <div>
              <div className="project-row__title">{sc.name}</div>
              <div className="project-row__sub">
                Forked {new Date(sc.created_at).toLocaleDateString("en-IN")}
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn btn--sm btn--day"
                onClick={() => activate.mutate(sc.id)}
              >
                Activate
              </button>
              <button
                className="btn btn--sm btn--ghost"
                onClick={() => remove.mutate(sc.id)}
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
