"use client";
import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import NavBar from "@/components/nav/NavBar";
import ProjectNav from "@/components/nav/ProjectNav";
import FlagsDrawer from "@/components/flags/FlagsDrawer";
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
