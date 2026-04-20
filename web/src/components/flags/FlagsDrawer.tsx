"use client";
import { useFlagsStore } from "@/stores/flags";
import { resolveFlag } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

const RULE_LABELS: Record<string, string> = {
  cast_holds: "Cast Hold",
  permit_leads: "Permit Lead Time",
  weather: "Weather Risk",
  drone_nofly: "Drone No-Fly",
  cost_overruns: "Budget Overrun",
  missing_data: "Missing Data",
  continuity: "Continuity Break",
};

export default function FlagsDrawer({ projectId }: { projectId: string }) {
  const { flags, drawerOpen, closeDrawer, removeFlag } = useFlagsStore();
  const qc = useQueryClient();

  if (!drawerOpen) return null;

  const openFlags = flags.filter((f) => !f.resolved_at);

  const handleResolve = async (flagId: string) => {
    await resolveFlag(projectId, flagId);
    removeFlag(flagId);
    qc.invalidateQueries({ queryKey: ["flags", projectId] });
  };

  return (
    <>
      <div
        className="modal-scrim"
        style={{ justifyItems: "end", alignItems: "start" }}
        onClick={closeDrawer}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100vh",
          width: "400px",
          background: "var(--chalk)",
          borderLeft: "var(--rule)",
          zIndex: 110,
          overflowY: "auto",
          padding: "32px 28px",
        }}
      >
        <div className="row" style={{ marginBottom: "24px" }}>
          <span className="lbl">Flags</span>
          <button onClick={closeDrawer} className="mono-xs">
            Close ×
          </button>
        </div>

        {openFlags.length === 0 && (
          <p className="voice" style={{ fontSize: "15px" }}>
            No open flags.
          </p>
        )}

        <div className="stack-sm">
          {openFlags.map((flag) => (
            <div key={flag.id} className="card" style={{ padding: "16px 18px" }}>
              <div className="row" style={{ marginBottom: "6px" }}>
                <span className="meta meta--red">
                  {RULE_LABELS[flag.rule] ?? flag.rule}
                </span>
                <span className="pill" style={{ fontSize: "10px" }}>
                  {flag.severity}
                </span>
              </div>
              <p style={{ fontFamily: "var(--serif)", fontSize: "14px", margin: "0 0 10px" }}>
                {flag.message}
              </p>
              <button
                className="btn btn--sm btn--ghost"
                onClick={() => handleResolve(flag.id)}
              >
                Resolve
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
