"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: 1.6,
                 strokeLinecap: "round", strokeLinejoin: "round" } as const;

const ICONS: Record<string, React.ReactNode> = {
  calendar: (
    <svg width="17" height="17" viewBox="0 0 24 24" {...STROKE}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
      <path d="M3.5 10h17M8 2.8V6.6M16 2.8V6.6" />
    </svg>
  ),
  schedule: (
    <svg width="17" height="17" viewBox="0 0 24 24" {...STROKE}>
      <path d="M8.5 6h12M8.5 12h12M8.5 18h12" />
      <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none" />
    </svg>
  ),
  expenses: (
    <svg width="17" height="17" viewBox="0 0 24 24" {...STROKE}>
      <path d="M6 2.8h12v18.4l-2.4-1.6-2.4 1.6-1.2-.8-1.2.8-2.4-1.6L6 21.2z" />
      <path d="M9.5 8h5M9.5 12h5" />
    </svg>
  ),
  activity: (
    <svg width="17" height="17" viewBox="0 0 24 24" {...STROKE}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2.2" />
    </svg>
  ),
};

/** Desktop workspace sidebar — the glass panel on the left of the shell. */
export default function WorkspaceSidebar({
  projectId,
  title,
}: {
  projectId: string;
  title: string;
}) {
  const pathname = usePathname();
  const base = `/project/${projectId}`;
  const items = [
    { key: "calendar", label: "Calendar", href: `${base}/calendar` },
    { key: "schedule", label: "Schedule", href: `${base}/schedule` },
    { key: "expenses", label: "Expenses", href: `${base}/expenses` },
    { key: "activity", label: "Activity", href: `${base}/activity` },
  ];

  return (
    <aside className="gq2-side">
      <img src="/moty-logo.jpg" alt="GQ Men of the Year" className="gq2-side__logo" />
      <div className="gq2-side__ws">
        <div className="gq2-side__wsname">{title}</div>
        <Link href="/" className="gq2-side__switch">
          Switch workspace ⇄
        </Link>
      </div>
      <nav className="gq2-side__nav">
        {items.map((it) => (
          <Link
            key={it.key}
            href={it.href}
            className={`gq2-side__item${pathname.startsWith(it.href) ? " is-active" : ""}`}
          >
            {ICONS[it.key]}
            {it.label}
          </Link>
        ))}
      </nav>
      <div className="gq2-side__foot">
        <ThemeToggle />
      </div>
    </aside>
  );
}
