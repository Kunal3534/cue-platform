"use client";
import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import NavBar from "@/components/nav/NavBar";
import ProjectNav from "@/components/nav/ProjectNav";
import FlagsDrawer from "@/components/flags/FlagsDrawer";
import Masthead from "@/components/editorial/Masthead";
import WorkspaceSidebar from "@/components/editorial/WorkspaceSidebar";
import UserChip from "@/components/editorial/UserChip";
import { useProjectStore } from "@/stores/project";
import { useProjectEvents } from "@/lib/sse/useProjectEvents";
import { getProject } from "@/lib/api";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const projectId = params.id as string;

  const setProject = useProjectStore((s) => s.setProject);

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  useEffect(() => {
    if (project) setProject(project);
  }, [project, setProject]);

  // Flags are populated by SSE (`flag_raised` event). The backend does not
  // expose a GET flags endpoint yet, so we don't fetch them on mount.

  useProjectEvents(projectId);

  if (!project) {
    return <div style={{ minHeight: "100vh" }} />;
  }

  // Editorial projects get the workspace shell: glass sidebar on desktop,
  // the masthead + pill tabs on phones. No film machinery either way.
  if (project.settings?.mode === "editorial") {
    return (
      <div className="gq-page">
        <div className="gq2-wrap">
          <WorkspaceSidebar projectId={projectId} title={project.title} />
          <div className="gq2-main gq-inner">
            <header className="gq2-top">
              <div className="gq2-top__crumb">November 2026 · Shoot calendar</div>
              <UserChip />
            </header>
            <div className="gq2-mobile-head">
              <Masthead projectId={projectId} />
            </div>
            <main style={{ paddingBottom: "64px" }}>{children}</main>
            <div className="gq-foot">Produced on Cue</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <NavBar />
      <ProjectNav projectId={projectId} />
      <main className="page" style={{ paddingBottom: "80px" }}>
        {children}
      </main>
      <FlagsDrawer />
    </>
  );
}
