"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listProjects, createEditorialWorkspace, getMe } from "@/lib/api";
import UserChip from "@/components/editorial/UserChip";
import ThemeToggle from "@/components/editorial/ThemeToggle";

/** Signed out, this is Cue's public homepage (Google's verification crawler
 *  needs to see what the app is without logging in). Signed in, it's the
 *  Workspaces screen. */
export default function HomePage() {
  const { data: me, isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
    staleTime: 60_000,
  });

  if (isLoading) {
    return <div className="gq-page" style={{ minHeight: "100vh" }} />;
  }
  return me && !isError ? <WorkspacesHome /> : <PublicLanding />;
}

function PublicLanding() {
  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ maxWidth: 760, paddingBottom: 60 }}>
        <header className="gq2-home-top">
          <div className="gq2-home-brand">
            CUE <span>·</span> CUEIT.IO
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <ThemeToggle />
            <Link href="/login" className="gq-share-btn" style={{ textDecoration: "none" }}>
              Sign in
            </Link>
          </div>
        </header>

        <div style={{ padding: "40px 0 10px" }}>
          <img src="/cue-mark.svg" alt="Cue" style={{ width: 84, height: 84, marginBottom: 22 }} />
          <h1 className="gq2-home-title" style={{ fontSize: 52, lineHeight: 1.05 }}>
            The production workspace for editorial shoots
          </h1>
          <p style={{ fontSize: 16.5, lineHeight: 1.75, maxWidth: 560, marginTop: 18 }}>
            Cue is where a magazine shoot runs: the calendar, the day briefs,
            the team and the money — in one place, built for producers.
          </p>
        </div>

        <div className="gq2-ws-grid" style={{ marginTop: 34 }}>
          <div className="gq2-ws-card">
            <div className="gq2-ws-card__eyebrow">Calendar &amp; briefs</div>
            <div className="gq2-ws-card__title">Every shoot day, briefed</div>
            <div className="gq2-ws-card__meta">
              Talent, call times, locations, moodboards — shareable with anyone
              via a read-only link, synced to Google Calendar.
            </div>
          </div>
          <div className="gq2-ws-card">
            <div className="gq2-ws-card__eyebrow">Team &amp; invites</div>
            <div className="gq2-ws-card__title">The right access for everyone</div>
            <div className="gq2-ws-card__meta">
              Producers edit, contributors view, guests get emailed day briefs
              and calendar invites.
            </div>
          </div>
          <div className="gq2-ws-card">
            <div className="gq2-ws-card__eyebrow">Expenses</div>
            <div className="gq2-ws-card__title">Receipts read themselves</div>
            <div className="gq2-ws-card__meta">
              Photograph a receipt and Cue extracts the spend, classifies it,
              and exports a Google Slides report for accounts.
            </div>
          </div>
          <div className="gq2-ws-card">
            <div className="gq2-ws-card__eyebrow">Invitation only</div>
            <div className="gq2-ws-card__title">Closed by design</div>
            <div className="gq2-ws-card__meta">
              Workspaces are private to their production teams. If you’ve been
              invited, sign in with Google or your email.
            </div>
          </div>
        </div>

        <div style={{ marginTop: 40 }}>
          <Link href="/login" className="gq-btn" style={{ textDecoration: "none" }}>
            Sign in to your workspace
          </Link>
        </div>

        <p style={{ marginTop: 44, fontSize: 12.5, color: "var(--g-muted)" }}>
          <Link href="/privacy" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
            Privacy Policy
          </Link>
          {" · "}
          <Link href="/terms" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
            Terms of Service
          </Link>
          {" · "}
          <a href="mailto:cue@cueit.io" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
            cue@cueit.io
          </a>
        </p>

        <div className="gq-foot">Produced on Cue</div>
      </div>
    </div>
  );
}

function WorkspacesHome() {
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
          Every production you&rsquo;re part of lives in its own workspace — calendar,
          briefings, expenses and the team around it.
        </p>

        {isLoading ? (
          <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>
        ) : isError ? (
          <div className="gq2-ws-card" style={{ marginTop: 36, textAlign: "center" }}>
            <p style={{ color: "#999" }}>
              Couldn&rsquo;t load workspaces
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
