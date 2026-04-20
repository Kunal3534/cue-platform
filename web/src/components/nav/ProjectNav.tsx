"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { label: "Chat", href: "" },
  { label: "Schedule", href: "/schedule" },
  { label: "Calendar", href: "/calendar" },
  { label: "Scenes", href: "/scenes" },
  { label: "Cast DOOD", href: "/resources/cast" },
  { label: "Resources", href: "/resources" },
  { label: "Call Sheets", href: "/callsheets" },
  { label: "Edit Master", href: "/master" },
  { label: "Scenarios", href: "/scenarios" },
] as const;

export default function ProjectNav({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const base = `/project/${projectId}`;

  return (
    <nav className="tabs">
      {TABS.map((tab) => {
        const href = `${base}${tab.href}`;
        const active =
          tab.href === ""
            ? pathname === base
            : pathname.startsWith(`${base}${tab.href}`);
        return (
          <Link
            key={tab.label}
            href={href}
            className={`tab${active ? " is-active" : ""}`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
