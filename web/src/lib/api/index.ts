import { apiFetch, apiUpload } from "./client";
import type {
  ProjectSummary,
  ProjectDetail,
  UserProfile,
  MainScheduleResponse,
  CalendarResponse,
  CastDoodResponse,
  ScenesMatrixResponse,
  PreviewResponse,
  CommitResponse,
  Scenario,
  ChatThread,
  ChatMessage,
  CallSheetSummary,
  EditItem,
  ResourceItem,
  SharedCalendarResponse,
  EditorialScheduleResponse,
  EditorialDay,
  EditorialMarker,
  ShootDayInput,
  TodoItem,
  ExpensesResponse,
  ExpenseItem,
  ExpenseInput,
  ExpensePatch,
  ActivityItem,
} from "./types";

// Auth
export const getMe = () => apiFetch<UserProfile>("/auth/me");

export const requestMagicLink = (email: string) =>
  apiFetch<{ ok: boolean; dev_link?: string }>("/auth/request_link", {
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
  return apiUpload<ProjectDetail>("/projects", form);
};

export const getProject = (id: string) =>
  apiFetch<ProjectDetail>(`/projects/${id}`);

export const deleteProject = (id: string) =>
  apiFetch<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" });

// Views
const q = (scenarioId?: string) =>
  scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : "";

export const getMainSchedule = (id: string, scenarioId?: string) =>
  apiFetch<MainScheduleResponse>(
    `/projects/${id}/views/main_schedule${q(scenarioId)}`,
  );

export const getCalendar = (id: string, scenarioId?: string) =>
  apiFetch<CalendarResponse>(
    `/projects/${id}/views/calendar${q(scenarioId)}`,
  );

// Editorial schedule (magazine shoots)
export const getEditorialSchedule = (id: string) =>
  apiFetch<EditorialScheduleResponse>(`/projects/${id}/editorial/schedule`);

export const upsertShootDay = (id: string, date: string, body: ShootDayInput) =>
  apiFetch<EditorialDay>(`/projects/${id}/editorial/days/${date}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const deleteShootDay = (id: string, date: string) =>
  apiFetch<void>(`/projects/${id}/editorial/days/${date}`, { method: "DELETE" });

export const moveShootDay = (id: string, from: string, to: string) =>
  apiFetch<EditorialDay>(`/projects/${id}/editorial/days/${from}/move`, {
    method: "POST",
    body: JSON.stringify({ to }),
  });

export const uploadMoodboard = (id: string, date: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<{ ok: boolean }>(`/projects/${id}/editorial/days/${date}/moodboard`, form);
};

export const moodboardUrl = (id: string, date: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/projects/${id}/editorial/days/${date}/moodboard`;

export const moodboardPageUrl = (id: string, date: string, page: number) =>
  `${moodboardUrl(id, date)}/pages/${page}`;

export const sharedMoodboardUrl = (token: string, date: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/share/${token}/moodboard/${date}`;

export const sharedMoodboardPageUrl = (token: string, date: string, page: number) =>
  `${sharedMoodboardUrl(token, date)}/pages/${page}`;

export const saveMarkers = (id: string, markers: EditorialMarker[]) =>
  apiFetch<{ markers: EditorialMarker[] }>(`/projects/${id}/markers`, {
    method: "PUT",
    body: JSON.stringify({ markers }),
  });

export const getTodos = (id: string) =>
  apiFetch<{ todos: TodoItem[] }>(`/projects/${id}/todos`);

export const saveTodos = (id: string, todos: TodoItem[]) =>
  apiFetch<{ todos: TodoItem[] }>(`/projects/${id}/todos`, {
    method: "PUT",
    body: JSON.stringify({ todos }),
  });

// Expenses (producer-only — never on share links)
export const getExpenses = (id: string) =>
  apiFetch<ExpensesResponse>(`/projects/${id}/expenses`);

export const createExpense = (id: string, body: ExpenseInput) =>
  apiFetch<ExpenseItem>(`/projects/${id}/expenses`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const uploadExpenseReceipt = (id: string, file: File, date?: string | null) => {
  const form = new FormData();
  form.append("file", file);
  if (date) form.append("date", date);
  return apiUpload<ExpenseItem>(`/projects/${id}/expenses/upload`, form);
};

export const updateExpense = (id: string, expenseId: string, body: ExpensePatch) =>
  apiFetch<ExpenseItem>(`/projects/${id}/expenses/${expenseId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteExpense = (id: string, expenseId: string) =>
  apiFetch<void>(`/projects/${id}/expenses/${expenseId}`, { method: "DELETE" });

export const rereadExpenseReceipt = (id: string, expenseId: string) =>
  apiFetch<{ ok: boolean }>(`/projects/${id}/expenses/${expenseId}/reread`, {
    method: "POST",
  });

export const expenseReceiptUrl = (id: string, expenseId: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/projects/${id}/expenses/${expenseId}/receipt`;

export const expenseReportUrl = (id: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/projects/${id}/expenses/report.pptx`;

// Activity log (producer-only)
export const getActivity = (id: string) =>
  apiFetch<{ items: ActivityItem[] }>(`/projects/${id}/activity`);

// Shoot invites (producer-only)
export const getInvites = (id: string, date: string) =>
  apiFetch<{ invites: import("./types").ShootInvite[] }>(
    `/projects/${id}/editorial/days/${date}/invites`,
  );

export const createInvite = (id: string, date: string, email: string, name?: string | null) =>
  apiFetch<import("./types").ShootInvite>(`/projects/${id}/editorial/days/${date}/invites`, {
    method: "POST",
    body: JSON.stringify({ email, name: name || null }),
  });

export const deleteInvite = (id: string, date: string, inviteId: string) =>
  apiFetch<void>(`/projects/${id}/editorial/days/${date}/invites/${inviteId}`, {
    method: "DELETE",
  });

export const googleLoginUrl = () =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/auth/google/login`;

export const getPickerConfig = () =>
  apiFetch<{ access_token: string; api_key: string }>("/auth/google/picker");

export const setMoodboardFromGoogle = (
  id: string,
  date: string,
  files: { id: string; name: string; mime_type: string }[],
) =>
  apiFetch<{ ok: boolean }>(`/projects/${id}/editorial/days/${date}/moodboard/google`, {
    method: "POST",
    body: JSON.stringify({ files }),
  });

export const exportReportToSlides = (id: string) =>
  apiFetch<{ url: string }>(`/projects/${id}/expenses/report/slides`, { method: "POST" });

// Share links
export const mintDayShareLink = (id: string, date: string) =>
  apiFetch<{ token: string; path: string }>(
    `/projects/${id}/editorial/days/${date}/share`,
    { method: "POST" },
  );

export const getSharedDay = (token: string) =>
  apiFetch<{ title: string; window: string | null; day: EditorialDay }>(
    `/share/day/${encodeURIComponent(token)}`,
  );

export const sharedDayMoodboardUrl = (token: string) =>
  `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/share/day/${token}/moodboard`;

export const sharedDayMoodboardPageUrl = (token: string, page: number) =>
  `${sharedDayMoodboardUrl(token)}/pages/${page}`;

export const mintShareLink = (id: string) =>
  apiFetch<{ token: string; path: string }>(`/projects/${id}/share`, {
    method: "POST",
  });

export const getSharedCalendar = (token: string) =>
  apiFetch<SharedCalendarResponse>(`/share/${encodeURIComponent(token)}`);

export const getCastDood = (id: string, scenarioId?: string) =>
  apiFetch<CastDoodResponse>(
    `/projects/${id}/views/cast_dood${q(scenarioId)}`,
  );

export const getScenesMatrix = (id: string, scenarioId?: string) =>
  apiFetch<ScenesMatrixResponse>(
    `/projects/${id}/views/scenes_matrix${q(scenarioId)}`,
  );

// Edits
export const previewEdits = (
  projectId: string,
  edits: EditItem[],
  scenarioId?: string,
) =>
  apiFetch<PreviewResponse>(`/projects/${projectId}/edits`, {
    method: "POST",
    body: JSON.stringify({ edits, scenario_id: scenarioId ?? null }),
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
  orderInDay: number = 1,
) =>
  apiFetch<PreviewResponse>(
    `/projects/${projectId}/scenes/${sceneId}/reschedule`,
    {
      method: "POST",
      body: JSON.stringify({ to_day_id: toDayId, order_in_day: orderInDay }),
    },
  );

// Scenarios
export const listScenarios = (projectId: string) =>
  apiFetch<Scenario[]>(`/projects/${projectId}/scenarios`);

export const forkScenario = (
  projectId: string,
  name: string,
  notes?: string,
) =>
  apiFetch<Scenario>(`/projects/${projectId}/scenarios`, {
    method: "POST",
    body: JSON.stringify({ name, notes: notes ?? null }),
  });

export const deleteScenario = (projectId: string, scenarioId: string) =>
  apiFetch<{ ok: boolean }>(
    `/projects/${projectId}/scenarios/${scenarioId}`,
    { method: "DELETE" },
  );

export const mergeScenario = (projectId: string, scenarioId: string) =>
  apiFetch<CommitResponse>(
    `/projects/${projectId}/scenarios/${scenarioId}/merge`,
    { method: "POST" },
  );

export const getScenarioDiff = (projectId: string, scenarioId: string) =>
  apiFetch<unknown>(
    `/projects/${projectId}/scenarios/${scenarioId}/diff`,
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
  apiFetch<CallSheetSummary[]>(`/projects/${projectId}/callsheets`);

// Returns a presigned PDF URL for a given call sheet.
// The backend route is GET /callsheets/{call_sheet_id}/pdf and typically
// returns a redirect to an S3 URL. We pass through the JSON response shape.
export const getCallSheetPdf = (projectId: string, callSheetId: string) =>
  apiFetch<{ url: string }>(
    `/projects/${projectId}/callsheets/${callSheetId}/pdf`,
  );

export const generateCallSheet = (
  projectId: string,
  dayId: string,
  opts?: { scenarioId?: string; sync?: boolean },
) => {
  const params = new URLSearchParams();
  if (opts?.scenarioId) params.set("scenario_id", opts.scenarioId);
  if (opts?.sync) params.set("sync", "true");
  const qs = params.toString();
  return apiFetch<unknown>(
    `/projects/${projectId}/days/${dayId}/callsheets/generate${qs ? `?${qs}` : ""}`,
    { method: "POST" },
  );
};

export const sendCallSheet = (
  projectId: string,
  callSheetId: string,
  recipients: { name?: string; email: string }[],
) =>
  apiFetch<{ queued: boolean; job_id: string | null }>(
    `/projects/${projectId}/callsheets/${callSheetId}/send`,
    {
      method: "POST",
      body: JSON.stringify({ recipients }),
    },
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
export const exportBundle = (projectId: string, scenarioId?: string) =>
  apiFetch<{ job_id: string; arq_job_id: string | null }>(
    `/projects/${projectId}/exports/bundle${q(scenarioId)}`,
    { method: "POST" },
  );

export const getBundleJob = (projectId: string, jobId: string) =>
  apiFetch<unknown>(
    `/projects/${projectId}/exports/bundle/${jobId}`,
  );

export const getViewExport = (
  projectId: string,
  view: string,
  scenarioId?: string,
) =>
  apiFetch<unknown>(
    `/projects/${projectId}/exports/${view}${q(scenarioId)}`,
  );
