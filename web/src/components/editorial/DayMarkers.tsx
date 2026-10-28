"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEditorialSchedule, saveMarkers } from "@/lib/api";
import type { EditorialMarker } from "@/lib/api/types";

/**
 * Special days on one date — festival holidays for everyone, or someone's
 * own day (birthday, leave). Producer-only surface; holidays also appear on
 * the share link, personal days never do.
 */
export default function DayMarkers({
  projectId,
  date,
}: {
  projectId: string;
  date: string;
}) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });

  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<"holiday" | "personal">("holiday");
  const [who, setWho] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  if (!data) return null;
  const dayMarkers = (data.markers ?? []).filter((m) => m.date === date);

  // Mutations rebase on a fresh fetch — a stale cached list must never
  // overwrite what the other producer just saved.
  const persist = async (update: (fresh: EditorialMarker[]) => EditorialMarker[]) => {
    setSaving(true);
    setError(false);
    try {
      const fresh = await qc.fetchQuery({
        queryKey: ["editorial-schedule", projectId],
        queryFn: () => getEditorialSchedule(projectId),
        staleTime: 0,
      });
      await saveMarkers(projectId, update(fresh.markers ?? []));
      await qc.invalidateQueries({ queryKey: ["editorial-schedule", projectId] });
      setAdding(false);
      setLabel("");
      setWho("");
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  };

  const addMarker = () => {
    if (!label.trim()) return;
    void persist((fresh) => [
      ...fresh,
      {
        id: crypto.randomUUID(),
        date,
        label: label.trim(),
        emoji: "✦", // legacy field — the UI renders ornaments now
        kind,
        who: kind === "personal" ? who.trim() || null : null,
      },
    ]);
  };

  return (
    <div style={{ marginTop: 44 }}>
      <div className="gq-moodboard__head">
        <span>Special days</span>
        <span style={{ color: "var(--g-muted)", textTransform: "none", letterSpacing: "0.04em" }}>
          holidays show on the share link · personal days stay private
        </span>
      </div>

      {dayMarkers.map((m) => (
        <div key={m.id} className={`gq-marker-chip gq-marker-chip--${m.kind}`}>
          {m.kind === "personal" ? (
            <span className="gq-marker__mono" aria-hidden>
              {(m.who || m.label).charAt(0).toUpperCase()}
            </span>
          ) : (
            <span className="gq-marker__orn gq-marker__orn--lg" aria-hidden>✦</span>
          )}
          <span className="gq-marker-chip__label">
            {m.label}
            {m.kind === "personal" && m.who ? ` — ${m.who}` : ""}
          </span>
          <button
            type="button"
            className="gq-todo__del"
            aria-label="Remove"
            onClick={() => void persist((fresh) => fresh.filter((x) => x.id !== m.id))}
          >
            ×
          </button>
        </div>
      ))}

      {adding ? (
        <div className="gq-marker-form">
          <div className="gq-form__grid">
            <div>
              <label className="gq-label">What is it?</label>
              <input
                className="gq-input"
                value={label}
                placeholder="Diwali · Birthday · Day off…"
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
            <div>
              <label className="gq-label">Who’s off?</label>
              <select
                className="gq-input"
                value={kind}
                onChange={(e) => setKind(e.target.value as "holiday" | "personal")}
              >
                <option value="holiday">Everyone — full holiday</option>
                <option value="personal">Just one person</option>
              </select>
            </div>
            {kind === "personal" && (
              <div>
                <label className="gq-label">Whose day?</label>
                <input
                  className="gq-input"
                  value={who}
                  placeholder="Shubhra"
                  onChange={(e) => setWho(e.target.value)}
                />
              </div>
            )}
          </div>
          {error && (
            <p style={{ color: "#C33", fontSize: 12, marginTop: 10 }}>Could not save — try again.</p>
          )}
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button type="button" className="gq-btn" onClick={addMarker} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" className="gq-btn gq-btn--ghost" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="gq-btn gq-btn--ghost"
          style={{ marginTop: 8, fontSize: 10, padding: "9px 16px" }}
          onClick={() => setAdding(true)}
        >
          + Add special day
        </button>
      )}
    </div>
  );
}
