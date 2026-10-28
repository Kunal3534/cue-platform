import Link from "next/link";
import ThemeToggle from "@/components/editorial/ThemeToggle";

/** Server-rendered public homepage. Cookieless visits to "/" are rewritten
 *  here by the middleware, so crawlers (including Google's OAuth
 *  verification) see real content without running any client JS. */
export const metadata = {
  title: "Cue — The production workspace for editorial shoots",
  description:
    "Cue is where a magazine shoot runs: the calendar, the day briefs, the team and the money — in one place, built for producers.",
};

export default function WelcomePage() {
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
          {/* eslint-disable-next-line @next/next/no-img-element */}
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
              Workspaces are private to their production teams. If you&rsquo;ve
              been invited, sign in with Google or your email.
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
