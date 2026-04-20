"use client";
import { useState } from "react";
import { commitEdits } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import type { PreviewResponse } from "@/lib/api/types";

interface Props {
  projectId: string;
  preview: PreviewResponse;
  onClose: () => void;
  onCommitted?: () => void;
}

const VIEW_LABELS: Record<string, string> = {
  main_schedule: "Main Schedule",
  calendar: "Calendar",
  scenes_matrix: "Scenes Matrix",
  cast_dood: "Cast DOOD",
};

export default function PreviewModal({ projectId, preview, onClose, onCommitted }: Props) {
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const { diff } = preview;
  const hasBreaks = diff.breaks && diff.breaks.length > 0;

  const handleCommit = async () => {
    setCommitting(true);
    setError(null);
    try {
      await commitEdits(projectId, preview.batch_id);
      for (const view of diff.views_affected) {
        qc.invalidateQueries({ queryKey: ["view", projectId, view] });
      }
      onCommitted?.();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Commit failed");
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__eyebrow">
          <span className="meta meta--red">Preview</span>
        </div>
        <h2 className="modal__title">Propagation Preview</h2>
        <p className="modal__body">
          These changes will affect the following views. Review before committing.
        </p>

        {hasBreaks && (
          <div
            style={{
              background: "var(--cue-red-10)",
              border: "1px solid var(--cue-red)",
              padding: "14px 18px",
              marginTop: "16px",
            }}
          >
            <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--cue-red)" }}>
              Hard breaks detected — cannot commit until resolved.
            </p>
          </div>
        )}

        {diff.views_affected.length > 0 && (
          <div className="modal__impact">
            {diff.views_affected.map((view) => (
              <div key={view} className="impact-row">
                <span className="impact-row__view">
                  {VIEW_LABELS[view] ?? view}
                </span>
                <span className="impact-row__desc">Will be regenerated</span>
                <span className="impact-row__count">affected</span>
              </div>
            ))}
          </div>
        )}

        {error && (
          <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--cue-red)", marginTop: "12px" }}>
            {error}
          </p>
        )}

        <div className="modal__actions">
          <button className="btn btn--ghost btn--sm" onClick={onClose} disabled={committing}>
            Discard
          </button>
          <button
            className="btn btn--primary btn--sm"
            onClick={handleCommit}
            disabled={committing || hasBreaks}
          >
            {committing ? "Committing…" : "Commit →"}
          </button>
        </div>
      </div>
    </div>
  );
}
