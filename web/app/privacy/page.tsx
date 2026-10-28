/** Public privacy policy — linked from the Google OAuth consent screen. */
export const metadata = { title: "Privacy Policy — Cue" };

const S = {
  h2: { fontFamily: "var(--serif)", fontSize: 20, margin: "34px 0 10px" } as const,
  p: { fontSize: 14.5, lineHeight: 1.75, margin: "0 0 12px" } as const,
};

export default function PrivacyPage() {
  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ maxWidth: 680, paddingBottom: 60 }}>
        <div style={{ padding: "48px 0 8px" }}>
          <p style={{ letterSpacing: "0.26em", fontSize: 11, color: "var(--g-gold)" }}>CUE</p>
          <h1 style={{ fontFamily: "var(--serif)", fontSize: 34, margin: "6px 0 4px" }}>
            Privacy Policy
          </h1>
          <p style={{ color: "var(--g-muted)", fontSize: 13 }}>Last updated 28 October 2026</p>
        </div>

        <h2 style={S.h2}>What Cue is</h2>
        <p style={S.p}>
          Cue is a production-scheduling workspace for editorial shoots, operated at
          cueit.io. Access is by invitation only: producers add the people who work
          on a production.
        </p>

        <h2 style={S.h2}>What we collect</h2>
        <p style={S.p}>
          Your name and email address when you sign in (with Google or an emailed
          link), and the content your team puts into a workspace: shoot schedules,
          call times, briefs, moodboards, expense records and receipts, notes, and
          the activity log of changes.
        </p>

        <h2 style={S.h2}>Google user data</h2>
        <p style={S.p}>
          If you connect Google, Cue uses your Google account only to: (1) verify
          your identity and email address at sign-in; (2) create and update events
          for your shoot days in your Google Calendar; (3) access only the specific
          Google Drive files you pick in the file chooser (for moodboards) and the
          Slides files Cue creates for you (expense reports). Cue never reads your
          inbox, your other calendar events, or the rest of your Drive.
        </p>
        <p style={S.p}>
          Cue&rsquo;s use and transfer of information received from Google APIs
          adheres to the{" "}
          <a
            href="https://developers.google.com/terms/api-services-user-data-policy"
            style={{ textDecoration: "underline", textUnderlineOffset: 3 }}
          >
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements. Google data is never sold,
          never used for advertising, and never read by humans except with your
          permission or for security and compliance.
        </p>

        <h2 style={S.h2}>How data is used and shared</h2>
        <p style={S.p}>
          Workspace content is visible to the team of that workspace according to
          each person&rsquo;s role. Receipt images a producer uploads are processed
          by an AI service (Anthropic) solely to extract the expense details. Emails
          (sign-in links, invitations, day briefs) are delivered via Resend. Data is
          hosted on Fly.io. We do not sell personal data to anyone.
        </p>

        <h2 style={S.h2}>Retention and deletion</h2>
        <p style={S.p}>
          Workspace data is kept while the production is active. To have your
          account or a workspace&rsquo;s data corrected or deleted, or to disconnect
          Google access at any time (also possible from your Google Account&rsquo;s
          security settings), contact us below.
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
