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

export interface LocationRef {
  id: string;
  name: string;
  area: string;
  kind: string;
}

export interface CameraUnit {
  unit_code: string;
  kind: string;
  count: number;
}

export interface MainScheduleScene {
  scene_id: string;
  scene_number: string;
  title: string;
  dn: string;
  page_eighths: number | null;
  setups_est: number;
  order_in_day: number;
}

export interface MainScheduleDay {
  day_id: string;
  date: string;
  day_of_week: string;
  shoot_day_number: number | null;
  kind: string;
  location: LocationRef | null;
  scenes: MainScheduleScene[];
  cast: string[];
  camera_units: CameraUnit[];
  jr_count: number;
  shift_start: string | null;
  shift_end: string | null;
  notes: string | null;
}

export interface MainScheduleResponse {
  view: string;
  project_id: string;
  scenario_id: string | null;
  computed_at: string;
  days: MainScheduleDay[];
  meta: {
    total_days: number;
    shoot_days: number;
    start_date: string | null;
    end_date: string | null;
  };
}

export interface CalendarScene {
  scene_number: string;
  title: string;
  dn: string;
}

export interface CalendarDay {
  date: string;
  day_of_week: string;
  kind: string;
  shoot_day_number: number | null;
  location: string | null;
  scenes: CalendarScene[];
  scene_count: number;
  page_eighths_total: number | null;
  setups_total: number;
  jr_count: number;
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
  months: CalendarMonth[];
  unscheduled: CalendarScene[];
}

export interface CastDoodCharacter {
  character_id: string;
  canonical_name: string;
  display_name: string;
  actor_name: string;
  is_principal: boolean;
  days: Record<string, "W" | "H" | "T" | ".">;
  summary: { W: number; H: number; T: number };
}

export interface CastDoodShootDay {
  day_id: string;
  shoot_day_number: number;
  date: string;
  label: string;
}

export interface CastDoodResponse {
  shoot_days: CastDoodShootDay[];
  characters: CastDoodCharacter[];
  day_totals: Record<string, number>;
}

export interface ScenesMatrixScene {
  scene_id: string;
  scene_number: string;
  title: string;
  dn: string;
  page_eighths: number | null;
  characters: string[];
  day_numbers: number[];
}

export interface ScenesMatrixShootDay {
  day_id: string;
  shoot_day_number: number;
  date: string;
  label: string;
}

export interface ScenesMatrixResponse {
  shoot_days: ScenesMatrixShootDay[];
  scenes: ScenesMatrixScene[];
  meta: {
    total_pages_eighths: number;
    day_count: number;
    night_count: number;
    ext_count: number;
    int_count: number;
  };
}

export interface PreviewDiff {
  views_affected: string[];
  breaks: unknown[];
  side_effects: unknown[];
  flags_raised: unknown[];
  request?: unknown;
}

export interface PreviewResponse {
  batch_id: string;
  diff: PreviewDiff;
  expires_at: string;
}

export interface CommitResponse {
  ok: boolean;
  views_regenerated: Record<string, unknown>;
}

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
}

export interface ChatThread {
  id: string;
  project_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface CallSheet {
  id: string;
  project_id: string;
  day_id: string;
  shoot_day_number: number;
  date: string;
  s3_key: string | null;
  status: string;
  created_at: string;
}

export interface DayDetail {
  day_id: string;
  date: string;
  shoot_day_number: number | null;
  kind: string;
  location: LocationRef | null;
  scenes: MainScheduleScene[];
  cast: string[];
  jr_count: number;
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
  id?: string;
  fields?: Record<string, unknown>;
}
