"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listProjects, createEditorialWorkspace } from "@/lib/api";
import UserChip from "@/components/editorial/UserChip";
import ThemeToggle from "@/components/editorial/ThemeToggle";

export default function WorkspacesPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const createWorkspace = async () => {
    const title = newTitle.trim();
    if (!title) return;
    setBusy(true);
    setCreateError(null);
    try {
      const ws = await createEditorialWorkspace(title);
      router.push(`/project/${ws.id}/calendar`);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Could not create the workspace");
      setBusy(false);
    }
  };
  // Client-side on purpose: the API is reached same-origin under /api with
  // the session cookie. (A server component here can do neither — that bug
  // once showed everyone an empty list.)
  const { data: projects, isLoading, isError, error } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    retry: 1,
  });

  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ paddingBottom: 60 }}>
        <header className="gq2-home-top">
          <div className="gq2-home-brand">
            CUE <span>·</span> WORKSPACES
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <ThemeToggle />
            <UserChip />
          </div>
        </header>

        <h1 className="gq2-home-title">Workspaces</h1>
        <p className="gq-exp-note" style={{ maxWidth: 480 }}>
          Every production you’re part of lives in its own workspace — calendar,
          briefings, expenses and the team around it.
        </p>

        {isLoading ? (
          <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>
        ) : isError ? (
          <div className="gq2-ws-card" style={{ marginTop: 36, textAlign: "center" }}>
            <p style={{ color: "#999" }}>
              Couldn’t load workspaces
              {error instanceof Error ? ` — ${error.message}` : ""}.
            </p>
            <Link href="/login" className="gq-btn" style={{ marginTop: 16 }}>
              Sign in again
            </Link>
          </div>
        ) : !projects || projects.length === 0 ? (
          <div className="gq2-ws-card" style={{ marginTop: 36, textAlign: "center" }}>
            <p style={{ color: "#999" }}>No workspaces yet.</p>
          </div>
        ) : (
          <section className="gq2-ws-grid">
            {projects.map((p) => (
              <Link key={p.id} href={`/project/${p.id}`} className="gq2-ws-card">
                <div className="gq2-ws-card__eyebrow">Workspace</div>
                <div className="gq2-ws-card__title">{p.title}</div>
                <div className="gq2-ws-card__meta">
                  {p.window || "In production"}
                  {p.shoot_days > 0 && ` · ${p.shoot_days} shoot day${p.shoot_days === 1 ? "" : "s"}`}
                </div>
                <span className="gq2-ws-card__open">Open workspace →</span>
              </Link>
            ))}
            {creating ? (
              <div className="gq2-ws-card gq2-ws-card--new" style={{ textAlign: "left" }}>
                <div className="gq2-ws-card__eyebrow">New workspace</div>
                <div className="gq2-ws-form">
                  <input
                    className="gq-input"
                    value={newTitle}
                    placeholder="e.g. Vogue — Wedding Issue 2027"
                    autoFocus
                    onChange={(e) => setNewTitle(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && createWorkspace()}
                  />
                  {createError && (
                    <p style={{ color: "#C33", fontSize: 12, margin: 0 }}>{createError}</p>
                  )}
                  <div style={{ display: "flex", gap: 10 }}>
                    <button type="button" className="gq-btn" onClick={createWorkspace}
                            disabled={busy} style={{ padding: "10px 22px", fontSize: 10 }}>
                      {busy ? "Creating…" : "Create"}
                    </button>
                    <button type="button" className="gq-btn gq-btn--ghost"
                            onClick={() => setCreating(false)}
                            style={{ padding: "10px 22px", fontSize: 10 }}>
                      Cancel
                    </button>
                  </div>
                  <Link href="/projects/new" className="gq-kv__sub"
                        style={{ fontSize: 11, textDecoration: "underline", textUnderlineOffset: 3 }}>
                    or start a film project from a master breakdown
                  </Link>
                </div>
              </div>
            ) : (
              <button type="button" className="gq2-ws-card gq2-ws-card--new"
                      onClick={() => setCreating(true)}
                      style={{ cursor: "pointer", font: "inherit", color: "inherit" }}>
                <div className="gq2-ws-card__plus">+</div>
                <div className="gq2-ws-card__title" style={{ fontSize: 18 }}>
                  New workspace
                </div>
                <div className="gq2-ws-card__meta">A fresh calendar for another production</div>
              </button>
            )}
          </section>
        )}

        <div className="gq-foot">Produced on Cue</div>
      </div>
    </div>
  );
}
