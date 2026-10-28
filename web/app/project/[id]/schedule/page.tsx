"use client";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getMainSchedule, getEditorialSchedule } from "@/lib/api";
import { useProjectStore } from "@/stores/project";
import { useIsEditorial } from "@/lib/terminology";
import type { MainScheduleDay } from "@/lib/api/types";

function dnClass(dn: string | null | undefined): string {
  const d = (dn ?? "").toLowerCase();
  if (d.includes("night")) return d.includes("int") ? "strip-badge--night-int" : "strip-badge--night";
  if (d.includes("int")) return "strip-badge--day-int";
  if (d.includes("dusk") || d.includes("dawn")) return "strip-badge--dusk";
  return "";
}

function pagesLabel(eighths: number | null): string {
  if (eighths === null) return "—";
  const whole = Math.floor(eighths / 8);
  const rem = eighths % 8;
  if (whole === 0) return `⅛×${rem}`;
  if (rem === 0) return `${whole}`;
  return `${whole}⅛×${rem}`;
}

function ShootDayRow({ day }: { day: MainScheduleDay }) {
  const totalEighths = day.scenes.reduce((s, sc) => s + (sc.page_eighths ?? 0), 0);
  const dn = day.scenes[0]?.dn ?? "";

  return (
    <div className="schedule__row">
      <div>
        <div className="cell__date">
          {new Date(day.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
        </div>
        <div style={{ marginTop: "8px" }}>
          <span className={`strip-badge ${dnClass(dn)}`}>
            Day {day.shoot_day_number}
          </span>
        </div>
        <div className="unit-chips" style={{ marginTop: "6px" }}>
          {day.camera_units.map((u) => (
            <span key={u.unit_code} className={`unit-chip${u.kind === "aerial" ? " unit-chip--hot" : ""}`}>
              {u.unit_code}
            </span>
          ))}
        </div>
      </div>

      <div className="cell__location">
        {day.location ? (
          <>
            <div className="cell__location-primary">{day.location.name}</div>
            <div className="cell__location-sub">{day.location.area}</div>
          </>
        ) : (
          <span style={{ color: "var(--slate-30)", fontStyle: "italic" }}>—</span>
        )}
      </div>

      <div>
        {day.scenes.map((sc) => (
          <div key={sc.scene_id} style={{ marginBottom: "4px" }}>
            <span
              className="mono-xs"
              style={{ color: "var(--cue-red)", marginRight: "6px" }}
            >
              {sc.scene_number}
            </span>
            <span style={{ fontFamily: "var(--serif)", fontSize: "14px" }}>
              {sc.title}
            </span>
          </div>
        ))}
      </div>

      <div className="cell__shift">
        {day.shift_start && day.shift_end
          ? `${day.shift_start} – ${day.shift_end}`
          : "—"}
        <div style={{ marginTop: "4px", color: "var(--slate-50)", fontSize: "11px" }}>
          {pagesLabel(totalEighths)} pages
        </div>
      </div>

      <div className="cell__cast">
        {day.cast.join(", ") || "—"}
        {(day.jr_count ?? 0) > 0 && (
          <div className="cell__cast-supp">+{day.jr_count} juniors</div>
        )}
      </div>

      <div className="cell__notes">{day.notes || ""}</div>
    </div>
  );
}

export default function SchedulePage() {
  const isEditorial = useIsEditorial();
  return isEditorial ? <GqSchedulePage /> : <FilmSchedulePage />;
}

function GqSchedulePage() {
  const params = useParams();
  const projectId = params.id as string;
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });

  if (isLoading || !data) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ borderTop: "1px solid #111" }}>
        {data.days.map((day) => {
          const d = new Date(`${day.date}T00:00:00`);
          return (
            <div
              key={day.date}
              className="gq-sched-row"
              onClick={() => router.push(`/project/${projectId}/day/${day.date}`)}
            >
              <div className="gq-sched-row__date">
                {d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                <div className="gq-sched-row__meta">{day.day_of_week}</div>
              </div>
              <div className="gq-sched-row__talent">
                {day.talent.map((t) => (
                  <div key={t.name}>{t.name}</div>
                ))}
                <div className="gq-sched-row__meta" style={{ marginTop: 4 }}>
                  Photos + Film
                </div>
              </div>
              <div className="gq-sched-row__meta">
                {day.location.name}
                {day.location.area ? ` · ${day.location.area}` : ""}
              </div>
              <div className="gq-sched-row__meta">
                {day.call_time ? `Call ${day.call_time}` : ""}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilmSchedulePage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data, isLoading, error } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  if (isLoading) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading schedule…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="mono-xs" style={{ color: "var(--cue-red)" }}>
          Failed to load schedule.
        </p>
      </div>
    );
  }

  const shootDays = data.days.filter((d) => d.kind === "shoot");
  const nonShootDays = data.days.filter((d) => d.kind !== "shoot");

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="row" style={{ marginBottom: "24px" }}>
        <div>
          <div className="meta meta--red" style={{ marginBottom: "4px" }}>
            Main Schedule
          </div>
          <div className="proj-head__sub">
            <span>{data.meta.shoot_days} shoot days</span>
            <span>{data.meta.total_days} total days</span>
            {data.meta.start_date && (
              <span>
                {new Date(data.meta.start_date).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
                {" – "}
                {data.meta.end_date &&
                  new Date(data.meta.end_date).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="schedule">
        <div className="schedule__row schedule__row--head">
          <div>Date</div>
          <div>Location</div>
          <div>Scenes</div>
          <div>Shift</div>
          <div>Cast</div>
          <div>Notes</div>
        </div>

        {data.days.map((day) => {
          if (day.kind !== "shoot") {
            return (
              <div key={day.day_id} className="schedule__row schedule__row--break">
                <span>{day.kind.toUpperCase()}</span>
                <em>
                  {new Date(day.date).toLocaleDateString("en-IN", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                  })}
                  {day.notes ? ` — ${day.notes}` : ""}
                </em>
              </div>
            );
          }
          return <ShootDayRow key={day.day_id} day={day} />;
        })}
      </div>
    </div>
  );
}
