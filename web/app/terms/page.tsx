/** Public terms of service — linked from the Google OAuth consent screen. */
export const metadata = { title: "Terms of Service — Cue" };

const S = {
  h2: { fontFamily: "var(--serif)", fontSize: 20, margin: "34px 0 10px" } as const,
  p: { fontSize: 14.5, lineHeight: 1.75, margin: "0 0 12px" } as const,
};

export default function TermsPage() {
  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ maxWidth: 680, paddingBottom: 60 }}>
        <div style={{ padding: "48px 0 8px" }}>
          <p style={{ letterSpacing: "0.26em", fontSize: 11, color: "var(--g-gold)" }}>CUE</p>
          <h1 style={{ fontFamily: "var(--serif)", fontSize: 34, margin: "6px 0 4px" }}>
            Terms of Service
          </h1>
          <p style={{ color: "var(--g-muted)", fontSize: 13 }}>Last updated 28 October 2026</p>
        </div>

        <h2 style={S.h2}>The service</h2>
        <p style={S.p}>
          Cue (cueit.io) is an invitation-only workspace for planning and running
          editorial productions: shoot calendars, day briefs, team access, invites,
          and expense tracking. By signing in you agree to these terms.
        </p>

        <h2 style={S.h2}>Accounts and acceptable use</h2>
        <p style={S.p}>
          You are responsible for activity under your account. Use Cue only for the
          production work you&rsquo;ve been invited to, and don&rsquo;t attempt to
          access workspaces or data beyond your role. Producers are responsible for
          the content their team uploads.
        </p>

        <h2 style={S.h2}>Your content</h2>
        <p style={S.p}>
          Schedules, briefs, moodboards, receipts and notes remain yours (or your
          organisation&rsquo;s). You grant Cue the rights needed to store, display
          and process that content to provide the service — nothing more. Connected
          Google services are used only as described in the{" "}
          <a href="/privacy" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
            Privacy Policy
          </a>
          .
        </p>

        <h2 style={S.h2}>Availability and liability</h2>
        <p style={S.p}>
          Cue is provided as-is, without warranties. To the fullest extent permitted
          by law, Cue&rsquo;s liability for any claim related to the service is
          limited to the amount you paid for it. We may suspend access that abuses
          the service or puts other users&rsquo; data at risk.
        </p>

        <h2 style={S.h2}>Changes</h2>
        <p style={S.p}>
          We may update these terms; material changes will be announced in the app.
          Continued use after a change means you accept the updated terms.
        </p>

        <h2 style={S.h2}>Contact</h2>
        <p style={S.p}>
          <a href="mailto:cue@cueit.io" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
            cue@cueit.io
          </a>
        </p>

        <div className="gq-foot">Produced on Cue</div>
      </div>
    </div>
  );
}
