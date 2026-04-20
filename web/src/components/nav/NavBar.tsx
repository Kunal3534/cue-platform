"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useFlagsStore } from "@/stores/flags";
import { useProjectStore } from "@/stores/project";

export default function NavBar() {
  const pathname = usePathname();
  const project = useProjectStore((s) => s.project);
  const openDrawer = useFlagsStore((s) => s.openDrawer);
  const flagCount = useFlagsStore((s) =>
    s.flags.filter((f) => !f.resolved_at).length,
  );

  const isProjectPage = pathname.startsWith("/project/");

  return (
    <nav className="nav">
      <div className="nav__inner">
        <div className="nav__left">
          <Link href="/" className="wordmark">
            <Image
              src="/cue-mark.svg"
              alt="Cue"
              width={160}
              height={56}
              priority
              style={{ height: "56px", width: "auto" }}
            />
          </Link>
          {isProjectPage && project && (
            <Link
              href={`/project/${project.id}`}
              className="font-serif text-slate"
              style={{ fontSize: "15px", letterSpacing: "-0.01em" }}
            >
              {project.title}
            </Link>
          )}
        </div>
        <div className="nav__right">
          {isProjectPage && flagCount > 0 && (
            <button
              onClick={openDrawer}
              className="pill pill--red"
              style={{ cursor: "pointer" }}
            >
              {flagCount} flag{flagCount !== 1 ? "s" : ""}
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
