"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

/**
 * GQ-flavoured masthead + the two-tab nav for editorial projects.
 * Text-only branding — no logo artwork.
 */
export default function Masthead({
  projectId,
  subtitle = "November 2026 · Shoot Calendar",
  role = "producer",
}: {
  projectId?: string;
  subtitle?: string;
  role?: string | null;
}) {
  const pathname = usePathname();
  const base = projectId ? `/project/${projectId}` : null;
  const producer = role !== "contributor";

  // Producer surfaces stay out of contributor tabs; tabs only ever render in
  // the authenticated app (share pages mount Masthead without a projectId).
  const tabs = base
    ? [
        { label: "Calendar", href: `${base}/calendar` },
        { label: "Schedule", href: `${base}/schedule` },
        ...(producer
          ? [
              { label: "Expenses", href: `${base}/expenses` },
              { label: "Activity", href: `${base}/activity` },
              { label: "Team", href: `${base}/team` },
            ]
          : []),
      ]
    : [];

  return (
    <header>
      <div className="gq-masthead">
        {/* Official MOTY lockup; multiply blend sinks its paper into ours.
            Inside a workspace it links back to the workspaces list. */}
        {projectId ? (
          <Link href="/">
            <img src="/moty-logo.jpg" alt="GQ Men of the Year" className="gq-masthead__logo" />
          </Link>
        ) : (
          <img src="/moty-logo.jpg" alt="GQ Men of the Year" className="gq-masthead__logo" />
        )}
        <div className="gq-masthead__sub">{subtitle}</div>
        {/* On phones the tab bar scrolls, so the switch floats up here instead */}
        <div className={`gq-theme-float${tabs.length > 0 ? " gq-theme-float--tabbed" : ""}`}>
          <ThemeToggle />
        </div>
      </div>
      {tabs.length > 0 && (
        <nav className="gq-tabs">
          {tabs.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className={`gq-tab${pathname.startsWith(t.href) ? " is-active" : ""}`}
            >
              {t.label}
            </Link>
          ))}
          <span className="gq-tabs__sep" aria-hidden />
          <span className="gq-tabs__switch">
            <ThemeToggle />
          </span>
        </nav>
      )}
    </header>
  );
}
