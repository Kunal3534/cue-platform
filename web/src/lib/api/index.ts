import { apiFetch, apiUpload } from "./client";
import type {
  ProjectSummary,
  MainScheduleResponse,
  CalendarResponse,
  CastDoodResponse,
  ScenesMatrixResponse,
  PreviewResponse,
  CommitResponse,
  Flag,
  Scenario,
  ChatThread,
  ChatMessage,
  CallSheet,
  EditItem,
  ResourceItem,
} from "./types";

// Auth
export const getMe = () => apiFetch<{ id: string; email: string }>("/auth/me");

export const requestMagicLink = (email: string) =>
  apiFetch<{ ok: boolean }>("/auth/request_link", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

export const signOut = () =>
  apiFetch<{ ok: boolean }>("/auth/signout", { method: "POST" });

// Projects
export const listProjects = () => apiFetch<ProjectSummary[]>("/projects");

export const createProject = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<ProjectSummary>("/projects", form);
};

export const getProject = (id: string) =>
  apiFetch<ProjectSummary>(`/projects/${id}`);

// Views
export const getMainSchedule = (id: string, scenarioId?: string) =>
  apiFetch<MainScheduleResponse>(
    `/projects/${id}/views/main_schedule${scenarioId ? `?scenario_id=${scenarioId}` : ""}`,
  );

export const getCalendar = (id: string, scenarioId?: string) =>
  apiFetch<CalendarResponse>(
    `/projects/${id}/views/calendar${scenarioId ? `?scenario_id=${scenarioId}` : ""}`,
  );

export const getCastDood = (id: string, scenarioId?: string) =>
  apiFetch<CastDoodResponse>(
    `/projects/${id}/views/cast_dood${scenarioId ? `?scenario_id=${scenarioId}` : ""}`,
  );

export const getScenesMatrix = (id: string, scenarioId?: string) =>
  apiFetch<ScenesMatrixResponse>(
    `/projects/${id}/views/scenes_matrix${scenarioId ? `?scenario_id=${scenarioId}` : ""}`,
  );

// Edits
export const previewEdits = (
  projectId: string,
  edits: EditItem[],
  scenarioId?: string,
) =>
  apiFetch<PreviewResponse>(`/projects/${projectId}/edits`, {
    method: "POST",
    body: JSON.stringify({ edits, scenario_id: scenarioId }),
  });

export const commitEdits = (projectId: string, batchId: string) =>
  apiFetch<CommitResponse>(
    `/projects/${projectId}/edits/${batchId}/commit`,
    { method: "POST" },
  );

export const rescheduleScene = (
  projectId: string,
  sceneId: string,
  toDayId: string,
  orderInDay: number,
) =>
  apiFetch<PreviewResponse>(
    `/projects/${projectId}/scenes/${sceneId}/reschedule`,
    {
      method: "POST",
      body: JSON.stringify({ to_day_id: toDayId, order_in_day: orderInDay }),
    },
  );

// Flags
export const getFlags = (projectId: string) =>
  apiFetch<Flag[]>(`/projects/${projectId}/flags`);

export const resolveFlag = (projectId: string, flagId: string) =>
  apiFetch<Flag>(`/projects/${projectId}/flags/${flagId}/resolve`, {
    method: "POST",
  });

// Scenarios
export const listScenarios = (projectId: string) =>
  apiFetch<Scenario[]>(`/projects/${projectId}/scenarios`);

export const forkScenario = (projectId: string, name: string) =>
  apiFetch<Scenario>(`/projects/${projectId}/scenarios`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });

export const deleteScenario = (projectId: string, scenarioId: string) =>
  apiFetch<{ ok: boolean }>(
    `/projects/${projectId}/scenarios/${scenarioId}`,
    { method: "DELETE" },
  );

export const activateScenario = (projectId: string, scenarioId: string) =>
  apiFetch<{ ok: boolean }>(
    `/projects/${projectId}/scenarios/${scenarioId}/activate`,
    { method: "POST" },
  );

// Chat
export const listThreads = (projectId: string) =>
  apiFetch<ChatThread[]>(`/projects/${projectId}/chat/threads`);

export const createThread = (projectId: string, title?: string) =>
  apiFetch<ChatThread>(`/projects/${projectId}/chat/threads`, {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });

export const getThread = (projectId: string, threadId: string) =>
  apiFetch<ChatMessage[]>(
    `/projects/${projectId}/chat/threads/${threadId}/messages`,
  );

// Call sheets
export const listCallSheets = (projectId: string) =>
  apiFetch<CallSheet[]>(`/projects/${projectId}/callsheets`);

export const getCallSheetUrl = (projectId: string, date: string) =>
  apiFetch<{ url: string }>(
    `/projects/${projectId}/callsheets/${date}/download`,
  );

export const regenerateCallSheet = (
  projectId: string,
  dayId: string,
) =>
  apiFetch<{ ok: boolean }>(
    `/projects/${projectId}/callsheets/${dayId}/regenerate`,
    { method: "POST" },
  );

// Resources (parameterised)
const RESOURCE_KINDS = [
  "cast",
  "junior_artists",
  "picture_vehicles",
  "camera_units",
  "props",
  "animals",
  "vfx_shots",
  "sfx_effects",
  "hmu_sessions",
  "wardrobe_looks",
  "art_builds",
  "permits",
] as const;

export type ResourceKind = (typeof RESOURCE_KINDS)[number];

export const listResources = (projectId: string, kind: ResourceKind) =>
  apiFetch<ResourceItem[]>(`/projects/${projectId}/resources/${kind}`);

export const createResource = (
  projectId: string,
  kind: ResourceKind,
  data: Record<string, unknown>,
) =>
  apiFetch<ResourceItem>(`/projects/${projectId}/resources/${kind}`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateResource = (
  projectId: string,
  kind: ResourceKind,
  resourceId: string,
  data: Record<string, unknown>,
) =>
  apiFetch<ResourceItem>(
    `/projects/${projectId}/resources/${kind}/${resourceId}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  );

export const deleteResource = (
  projectId: string,
  kind: ResourceKind,
  resourceId: string,
) =>
  apiFetch<{ ok: boolean }>(
    `/projects/${projectId}/resources/${kind}/${resourceId}`,
    { method: "DELETE" },
  );

// Exports
export const exportBundle = (projectId: string) =>
  apiFetch<{ url: string }>(`/projects/${projectId}/exports/bundle`, {
    method: "POST",
  });
