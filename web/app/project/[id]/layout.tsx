"use client";
import { useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import NavBar from "@/components/nav/NavBar";
import ProjectNav from "@/components/nav/ProjectNav";
import FlagsDrawer from "@/components/flags/FlagsDrawer";
import { useProjectStore } from "@/stores/project";
import { useFlagsStore } from "@/stores/flags";
import { useProjectEvents } from "@/lib/sse/useProjectEvents";
import { getProject, getFlags } from "@/lib/api";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const projectId = params.id as string;

  const setProject = useProjectStore((s) => s.setProject);
  const setFlags = useFlagsStore((s) => s.setFlags);

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: flags } = useQuery({
    queryKey: ["flags", projectId],
    queryFn: () => getFlags(projectId),
  });

  useEffect(() => {
    if (project) setProject(project);
  }, [project, setProject]);

  useEffect(() => {
    if (flags) setFlags(flags);
  }, [flags, setFlags]);

  useProjectEvents(projectId);

  return (
    <>
      <NavBar />
      <ProjectNav projectId={projectId} />
      <main className="page" style={{ paddingBottom: "80px" }}>
        {children}
      </main>
      <FlagsDrawer projectId={projectId} />
    </>
  );
}
