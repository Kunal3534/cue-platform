"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * GQ-flavoured masthead + the two-tab nav for editorial projects.
 * Text-only branding — no logo artwork.
 */
export default function Masthead({
  projectId,
  subtitle = "November 2026 · Shoot Calendar",
}: {
  projectId?: string;
  subtitle?: string;
}) {
  const pathname = usePathname();
  const base = projectId ? `/project/${projectId}` : null;

  const tabs = base
    ? [
        { label: "Calendar", href: `${base}/calendar` },
        { label: "Schedule", href: `${base}/schedule` },
      ]
    : [];

  return (
    <header>
      <div className="gq-masthead">
        {/* Official MOTY lockup; multiply blend sinks its paper into ours */}
        <img src="/moty-logo.jpg" alt="GQ Men of the Year" className="gq-masthead__logo" />
        <div className="gq-masthead__sub">{subtitle}</div>
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
        </nav>
      )}
    </header>
  );
}
