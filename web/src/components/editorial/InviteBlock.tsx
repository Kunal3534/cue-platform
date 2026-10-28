"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getInvites, createInvite, deleteInvite, getMe } from "@/lib/api";

/**
 * Who's coming to this shoot day — producer-only. Each invite sends an email
 * with the live day brief; when a producer's Google Calendar is connected the
 * guest also lands on the calendar event and gets a real calendar invite.
 */
export default function InviteBlock({
  projectId,
  date,
}: {
  projectId: string;
  date: string;
}) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["invites", projectId, date],
    queryFn: () => getInvites(projectId, date),
  });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 60_000 });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!data) return null;

  const add = async () => {
    const em = email.trim();
    if (!em) return;
    setSending(true);
    setError(null);
    try {
      await createInvite(projectId, date, em, name.trim() || null);
      setEmail("");
      setName("");
      await qc.invalidateQueries({ queryKey: ["invites", projectId, date] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the invite");
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ marginTop: 44 }}>
      <div className="gq-moodboard__head">
        <span>Who’s coming</span>
        <span style={{ color: "var(--g-muted)", textTransform: "none", letterSpacing: "0.04em" }}>
          invites email the day brief
          {me?.google_calendar_connected ? " + a calendar invite" : ""}
        </span>
      </div>

      {data.invites.map((inv) => (
        <div key={inv.id} className="gq2-invite">
          <span className="gq2-invite__avatar">
            {(inv.name || inv.email)[0].toUpperCase()}
          </span>
          <span className="gq2-invite__who">
            {inv.name || inv.email}
            {inv.name && <span className="gq-kv__sub"> {inv.email}</span>}
          </span>
          <span className="gq-exp-status gq-exp-status--review">Invited</span>
          <button
            type="button"
            className="gq-todo__del"
            aria-label="Remove invite"
            onClick={async () => {
              await deleteInvite(projectId, date, inv.id);
              await qc.invalidateQueries({ queryKey: ["invites", projectId, date] });
            }}
          >
            ×
          </button>
        </div>
      ))}

      <div className="gq2-invite-form">
        <input
          className="gq-input"
          type="email"
          value={email}
          placeholder="email@condenast.in"
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <input
          className="gq-input"
          value={name}
          placeholder="Name (optional)"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button type="button" className="gq-btn" onClick={add} disabled={sending}
                style={{ flex: "none" }}>
          {sending ? "Sending…" : "Invite"}
        </button>
      </div>
      {error && (
        <p style={{ color: "#C33", fontSize: 12, marginTop: 8 }}>{error}</p>
      )}
    </div>
  );
}
