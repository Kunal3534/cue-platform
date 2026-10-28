"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useIsEditorial } from "@/lib/terminology";

const FILM_TABS = [
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

// Editorial projects lead with the calendar and drop film-only departments.
const EDITORIAL_TABS = [
  { label: "Calendar", href: "/calendar" },
  { label: "Schedule", href: "/schedule" },
  { label: "Talent", href: "/resources/cast" },
  { label: "HMU", href: "/resources/hmu" },
  { label: "Wardrobe", href: "/resources/wardrobe" },
  { label: "Call Sheets", href: "/callsheets" },
  { label: "Chat", href: "" },
  { label: "Scenarios", href: "/scenarios" },
] as const;

export default function ProjectNav({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const isEditorial = useIsEditorial();
  const base = `/project/${projectId}`;
  const tabs = isEditorial ? EDITORIAL_TABS : FILM_TABS;

  return (
    <nav className="tabs">
      {tabs.map((tab) => {
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
