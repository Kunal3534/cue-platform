"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getMembers, addMember, removeMember } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

/** Workspace team — everyone here can sign in (Google or email link) and
 *  edit everything in this workspace. */
export default function TeamPage() {
  const params = useParams();
  const projectId = params.id as string;
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => getMembers(projectId),
  });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"producer" | "contributor">("contributor");
  const project = useProjectStore((s) => s.project);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    const em = email.trim();
    if (!em) return;
    setBusy(true);
    setError(null);
    try {
      await addMember(projectId, em, name.trim() || null, role);
      setEmail("");
      setName("");
      await qc.invalidateQueries({ queryKey: ["members", projectId] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add them");
    } finally {
      setBusy(false);
    }
  };

  if (project && project.my_role === "contributor") {
    return <p style={{ color: "#999", padding: "40px 0", textAlign: "center" }}>Producers only.</p>;
  }
  if (isLoading || !data) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  return (
    <div style={{ maxWidth: 680, margin: "0 auto" }}>
      <div className="gq-detail__date">Team</div>
      <div className="gq-detail__headline">Who can work in this workspace</div>
      <p className="gq-exp-note" style={{ maxWidth: 460 }}>
        Everyone added here can sign in with Google or an email link and edit
        the calendar, briefings and expenses. Shoot-day guests belong on each
        day’s “Who’s coming” instead.
      </p>

      <div style={{ marginTop: 30 }}>
        {data.members.length === 0 && (
          <p style={{ color: "#999", padding: "12px 0" }}>
            No members yet — the producers on the access list already have entry.
          </p>
        )}
        {data.members.map((m) => (
          <div key={m.id} className="gq2-invite">
            <span className="gq2-invite__avatar">
              {(m.name || m.email)[0].toUpperCase()}
            </span>
            <span className="gq2-invite__who">
              {m.name || m.email}
              {m.name && <span className="gq-kv__sub"> {m.email}</span>}
            </span>
            <span className={`gq-exp-status ${m.role === "producer" ? "gq-exp-status--review" : "gq-exp-status--reading"}`}>
              {m.builtin ? "core producer" : m.role}
            </span>
            {!m.builtin && (
              <button
                type="button"
                className="gq-todo__del"
                aria-label="Remove member"
                onClick={async () => {
                  if (!window.confirm(`Remove ${m.name || m.email} from the workspace?`)) return;
                  await removeMember(projectId, m.id);
                  await qc.invalidateQueries({ queryKey: ["members", projectId] });
                }}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="gq-form__sec" style={{ marginTop: 36 }}>Add someone</div>
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
        <select className="gq-input" value={role} style={{ flex: "none", width: 170 }}
                onChange={(e) => setRole(e.target.value as "producer" | "contributor")}>
          <option value="contributor">Contributor</option>
          <option value="producer">Producer</option>
        </select>
        <button type="button" className="gq-btn" onClick={add} disabled={busy}
                style={{ flex: "none" }}>
          {busy ? "Adding…" : "Add"}
        </button>
      </div>
      <p className="gq-exp-note">
        Producers can edit everything. Contributors see the calendar and day
        briefs, keep private notes, and can sync shoots to their Google
        Calendar — no editing, expenses or team access.
      </p>
      {error && <p style={{ color: "#C33", fontSize: 12, marginTop: 8 }}>{error}</p>}
    </div>
  );
}
