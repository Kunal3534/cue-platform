"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "@/lib/api";
import UserChip from "@/components/editorial/UserChip";
import ThemeToggle from "@/components/editorial/ThemeToggle";

export default function WorkspacesPage() {
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
            <Link href="/projects/new" className="gq2-ws-card gq2-ws-card--new">
              <div className="gq2-ws-card__plus">+</div>
              <div className="gq2-ws-card__title" style={{ fontSize: 18 }}>
                New workspace
              </div>
              <div className="gq2-ws-card__meta">Start from a film master breakdown</div>
            </Link>
          </section>
        )}

        <div className="gq-foot">Produced on Cue</div>
      </div>
    </div>
  );
}
