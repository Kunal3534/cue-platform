// Types mirror the backend OpenAPI schema. Keep in sync with /openapi.json.

export interface ProjectSummary {
  id: string;
  title: string;
  window: string | null;
  status: string;
  shoot_days: number;
  total_days: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends ProjectSummary {
  start_date: string | null;
  end_date: string | null;
  live_scenario_id: string | null;
  unit_cols: string[];
}

export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  created_at: string;
}

export interface ScheduleLocation {
  id: string | null;
  name: string | null;
  area: string | null;
  kind: string | null;
}

export interface ScheduleCameraUnit {
  unit_code: string;
  kind: string;
  count: number;
}

export interface ScheduleScene {
  scene_id: string;
  scene_number: string;
  title: string | null;
  dn: string | null;
  page_eighths: number | null;
  setups_est: number | null;
  order_in_day: number | null;
}

export interface ScheduleDay {
  day_id: string;
  date: string;
  day_of_week: string;
  shoot_day_number: number | null;
  kind: string;
  location: ScheduleLocation | null;
  scenes: ScheduleScene[];
  cast: string[];
  camera_units: ScheduleCameraUnit[];
  jr_count: number | null;
  shift_start: string | null;
  shift_end: string | null;
  notes: string | null;
}

export interface ScheduleMeta {
  total_days: number;
  shoot_days: number;
  start_date: string | null;
  end_date: string | null;
}

export interface MainScheduleResponse {
  view: string;
  project_id: string;
  scenario_id: string | null;
  computed_at: string;
  days: ScheduleDay[];
  meta: ScheduleMeta;
}

// Backwards-compatible alias for existing imports.
export type MainScheduleDay = ScheduleDay;
export type MainScheduleScene = ScheduleScene;
export type LocationRef = ScheduleLocation;
export type CameraUnit = ScheduleCameraUnit;

export interface CalendarSceneStrip {
  scene_number: string;
  title: string | null;
  dn: string | null;
}

export interface CalendarDay {
  date: string;
  day_of_week: string;
  kind: string | null;
  shoot_day_number: number | null;
  location: string | null;
  scenes: CalendarSceneStrip[];
  scene_count: number;
  page_eighths_total: number | null;
  setups_total: number | null;
  jr_count: number | null;
  shift_start: string | null;
  shift_end: string | null;
  banner_text: string | null;
}

export interface CalendarMonth {
  label: string;
  year: number;
  month: number;
  days: CalendarDay[];
}

export interface CalendarResponse {
  view: string;
  project_id: string;
  scenario_id: string | null;
  computed_at: string;
  months: CalendarMonth[];
  unscheduled: CalendarSceneStrip[];
}

// Back-compat alias
export type CalendarScene = CalendarSceneStrip;

export interface DoodCharacter {
  character_id: string;
  canonical_name: string;
  display_name: string | null;
  actor_name: string | null;
  is_principal: boolean;
  days: Record<string, string>;
  // Optional — backend may or may not emit summary totals.
  summary?: { W: number; H: number; T: number };
}

export interface DoodShootDay {
  day_id: string;
  shoot_day_number: number;
  date: string;
  label: string;
}

export interface CastDoodResponse {
  view: string;
  project_id: string;
  scenario_id: string | null;
  computed_at: string;
  shoot_days: DoodShootDay[];
  characters: DoodCharacter[];
  day_totals: Record<string, number>;
}

// Back-compat
export type CastDoodCharacter = DoodCharacter;
export type CastDoodShootDay = DoodShootDay;

export interface SceneMatrixScene {
  scene_id: string;
  scene_number: string;
  title: string | null;
  dn: string | null;
  page_eighths: number | null;
  characters: string[];
  day_numbers: number[];
}

export interface SceneMatrixMeta {
  total_pages_eighths: number | null;
  day_count: number;
  night_count: number;
  ext_count: number;
  int_count: number;
}

export interface ScenesMatrixResponse {
  view: string;
  project_id: string;
  scenario_id: string | null;
  computed_at: string;
  shoot_days: DoodShootDay[];
  scenes: SceneMatrixScene[];
  meta: SceneMatrixMeta;
}

// Back-compat
export type ScenesMatrixScene = SceneMatrixScene;
export type ScenesMatrixShootDay = DoodShootDay;

export interface PreviewDiff {
  views_affected: string[];
  breaks: unknown[];
  side_effects: unknown[];
  flags_raised: unknown[];
  // backend is intentionally loose (`extra=allow`).
  [key: string]: unknown;
}

export interface PreviewResponse {
  batch_id: string;
  diff: PreviewDiff;
  expires_at: string;
}

export interface CommitResponse {
  ok: boolean;
  views_regenerated: Record<string, unknown>;
  [key: string]: unknown;
}

// Flags: no backend endpoint yet; kept so the SSE `flag_raised` event + drawer
// UI continue to compile. When the API ships a flags route, we wire it up.
export interface Flag {
  id: string;
  project_id: string;
  rule: string;
  severity: string;
  message: string;
  entity_kind: string | null;
  entity_id: string | null;
  context: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}

export interface Scenario {
  id: string;
  project_id: string;
  name: string;
  forked_from: string | null;
  created_at: string;
  is_live: boolean;
  [key: string]: unknown;
}

export interface ChatThread {
  id: string;
  title: string | null;
  created_at: string;
  last_active_at: string;
  // Back-compat (older list UI expected updated_at/project_id)
  project_id?: string;
  updated_at?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string | null;
  tool_calls: unknown[] | null;
  edits_batch_id: string | null;
  created_at: string;
  // Some client-side synthesized messages still set thread_id.
  thread_id?: string;
}

export interface CallSheetSummary {
  id: string;
  day_id: string;
  version: number;
  status: string;
  pdf_s3_key: string | null;
  generated_at: string;
  sent_at: string | null;
}

// Back-compat alias (older UI called this "CallSheet")
export type CallSheet = CallSheetSummary;

export interface DayDetail {
  day_id: string;
  date: string;
  shoot_day_number: number | null;
  kind: string;
  location: ScheduleLocation | null;
  scenes: ScheduleScene[];
  cast: string[];
  jr_count: number | null;
  shift_start: string | null;
  shift_end: string | null;
  notes: string | null;
}

export interface ResourceItem {
  id: string;
  project_id: string;
  name: string;
  kind?: string;
  category?: string;
  day_assignments?: Record<string, number>;
  [key: string]: unknown;
}

export type EditOp = "patch" | "create" | "delete";

export interface EditItem {
  op: EditOp;
  entity: string;
  id?: string | null;
  fields?: Record<string, unknown> | null;
}
