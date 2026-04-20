import Link from "next/link";
import NavBar from "@/components/nav/NavBar";
import { listProjects } from "@/lib/api";
import type { ProjectSummary } from "@/lib/api/types";

async function getProjects(): Promise<ProjectSummary[]> {
  try {
    return await listProjects();
  } catch {
    return [];
  }
}

function initials(title: string): string {
  return title
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export default async function ProjectsPage() {
  const projects = await getProjects();

  return (
    <>
      <NavBar />
      <main className="page stack-lg" style={{ paddingTop: "56px" }}>
        <header className="row">
          <div>
            <div className="meta meta--red">All productions</div>
            <h1 className="display" style={{ marginTop: "12px" }}>
              Projects<span className="red">.</span>
            </h1>
          </div>
          <Link href="/projects/new" className="btn btn--primary">
            New project <span className="btn__arrow">→</span>
          </Link>
        </header>

        {projects.length === 0 ? (
          <div className="empty">
            <span className="empty__mark">CUE</span>
            <p className="voice" style={{ fontSize: "16px", marginTop: 0 }}>
              No projects yet. Upload a master breakdown to begin.
            </p>
            <Link
              href="/projects/new"
              className="btn btn--day"
              style={{ marginTop: "24px" }}
            >
              Upload master →
            </Link>
          </div>
        ) : (
          <section className="projects">
            {projects.map((p) => (
              <Link
                key={p.id}
                href={`/project/${p.id}`}
                className="project-row"
                style={{ textDecoration: "none" }}
              >
                <span className="project-row__chip">{initials(p.title)}</span>
                <div>
                  <div className="project-row__title">{p.title}</div>
                  <div className="project-row__sub">
                    {p.window || "Pre-production"}
                    {p.shoot_days > 0 && ` · ${p.shoot_days} shoot days`}
                  </div>
                </div>
                <div className="project-row__count">
                  <strong>{p.shoot_days || "—"}</strong>
                  {p.shoot_days ? "shoot days" : "not scheduled"}
                </div>
                <span className="project-row__open">Open →</span>
              </Link>
            ))}
          </section>
        )}
      </main>

      <footer className="foot">
        <div className="foot__inner">
          <span>Cue · v1</span>
          <span>Pre-production</span>
        </div>
      </footer>
    </>
  );
}
