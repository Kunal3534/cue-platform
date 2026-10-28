"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: 1.7,
                 strokeLinecap: "round", strokeLinejoin: "round" } as const;

const ICONS: Record<string, React.ReactNode> = {
  calendar: (
    <svg width="21" height="21" viewBox="0 0 24 24" {...STROKE}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
      <path d="M3.5 10h17M8 2.8V6.6M16 2.8V6.6" />
    </svg>
  ),
  schedule: (
    <svg width="21" height="21" viewBox="0 0 24 24" {...STROKE}>
      <path d="M8.5 6h12M8.5 12h12M8.5 18h12" />
      <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none" />
    </svg>
  ),
  expenses: (
    <svg width="21" height="21" viewBox="0 0 24 24" {...STROKE}>
      <path d="M6 2.8h12v18.4l-2.4-1.6-2.4 1.6-1.2-.8-1.2.8-2.4-1.6L6 21.2z" />
      <path d="M9.5 8h5M9.5 12h5" />
    </svg>
  ),
  activity: (
    <svg width="21" height="21" viewBox="0 0 24 24" {...STROKE}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2.2" />
    </svg>
  ),
  team: (
    <svg width="21" height="21" viewBox="0 0 24 24" {...STROKE}>
      <circle cx="9" cy="8.5" r="3.4" />
      <path d="M2.8 20a6.2 6.2 0 0 1 12.4 0" />
      <path d="M16 5.6a3.4 3.4 0 0 1 0 5.8M17.6 14.2a6.2 6.2 0 0 1 3.6 5.8" />
    </svg>
  ),
};

/** Phone navigation — fixed glass bar at the bottom, app style. */
export default function MobileTabBar({
  projectId,
  role = "producer",
}: {
  projectId: string;
  role?: string | null;
}) {
  const pathname = usePathname();
  const base = `/project/${projectId}`;
  const producer = role !== "contributor";
  const items = [
    { key: "calendar", label: "Calendar", href: `${base}/calendar` },
    { key: "schedule", label: "Schedule", href: `${base}/schedule` },
    ...(producer
      ? [
          { key: "expenses", label: "Expenses", href: `${base}/expenses` },
          { key: "activity", label: "Activity", href: `${base}/activity` },
          { key: "team", label: "Team", href: `${base}/team` },
        ]
      : []),
  ];
  return (
    <nav className="gq2-tabbar">
      {items.map((it) => (
        <Link
          key={it.key}
          href={it.href}
          className={`gq2-tabbar__item${pathname.startsWith(it.href) ? " is-active" : ""}`}
        >
          {ICONS[it.key]}
          <span>{it.label}</span>
        </Link>
      ))}
    </nav>
  );
}
