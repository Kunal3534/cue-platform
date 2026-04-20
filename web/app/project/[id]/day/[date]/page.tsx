"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getMainSchedule } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

function dnClass(dn: string): string {
  const d = dn.toLowerCase();
  if (d.includes("night")) return d.includes("int") ? "strip-badge--night-int" : "strip-badge--night";
  if (d.includes("int")) return "strip-badge--day-int";
  if (d.includes("dusk") || d.includes("dawn")) return "strip-badge--dusk";
  return "";
}

function dnStripClass(dn: string): string {
  const d = dn.toLowerCase();
  if (d.includes("night")) return "scene-strip__dn--night";
  if (d.includes("dusk") || d.includes("dawn")) return "scene-strip__dn--dusk";
  return "";
}

export default function DayDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const date = params.date as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  const day = data?.days.find((d) => d.date === date);

  if (isLoading) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading day…</p>
      </div>
    );
  }

  if (!day) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Day not found.</p>
        <Link href={`/project/${projectId}/schedule`} className="btn btn--ghost btn--sm" style={{ marginTop: "16px" }}>
          ← Schedule
        </Link>
      </div>
    );
  }

  const dn = day.scenes[0]?.dn ?? "";
  const totalEighths = day.scenes.reduce((s, sc) => s + (sc.page_eighths ?? 0), 0);

  return (
    <div style={{ paddingTop: "0" }}>
      <div className="day-hero">
        <div>
          <div className="day-hero__num">{day.shoot_day_number}</div>
          <div className="day-hero__lbl">Shoot Day</div>
          <div className="day-hero__date">
            {new Date(day.date).toLocaleDateString("en-IN", {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </div>
        </div>

        <div>
          <h1 className="day-hero__title">{day.location?.name ?? "—"}</h1>
          <div className="day-hero__sub">{day.location?.area ?? ""}</div>
          {day.shift_start && day.shift_end && (
            <div
              className="mono-sm"
              style={{ marginTop: "14px" }}
            >
              {day.shift_start} – {day.shift_end}
            </div>
          )}
        </div>

        <div className="day-hero__stats">
          <span>
            <strong>{totalEighths}⅛</strong>
            pages
          </span>
          <span>
            <strong>{day.scenes.length}</strong>
            scenes
          </span>
          <span>
            <strong>{day.cast.length}</strong>
            cast
          </span>
          {day.jr_count > 0 && (
            <span>
              <strong>{day.jr_count}</strong>
              juniors
            </span>
          )}
        </div>
      </div>

      <div className="day-section-title">Scenes</div>

      {day.scenes.map((sc) => (
        <div key={sc.scene_id} className="scene-strip">
          <div>
            <div className="scene-strip__num">{sc.scene_number}</div>
            <div className="scene-strip__pages">{sc.page_eighths ?? "—"}⅛</div>
            <div className="scene-strip__pages-sub">{sc.setups_est} setups</div>
          </div>
          <div>
            <span className={`scene-strip__dn ${dnStripClass(sc.dn)}`}>{sc.dn}</span>
          </div>
          <div>
            <div className="scene-strip__desc">{sc.title}</div>
          </div>
          <div className="scene-strip__time">
            {day.shift_start ?? "—"}
          </div>
        </div>
      ))}

      {day.cast.length > 0 && (
        <>
          <div className="day-section-title">Cast</div>
          <div style={{ paddingTop: "16px", display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {day.cast.map((name) => (
              <span key={name} className="element-chip element-chip--cast">{name}</span>
            ))}
            {day.jr_count > 0 && (
              <span className="element-chip">+{day.jr_count} juniors</span>
            )}
          </div>
        </>
      )}

      {day.camera_units.length > 0 && (
        <>
          <div className="day-section-title">Camera Units</div>
          <div style={{ paddingTop: "16px", display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {day.camera_units.map((u) => (
              <span key={u.unit_code} className={`unit-chip${u.kind === "aerial" ? " unit-chip--hot" : ""}`}>
                {u.unit_code} · {u.kind}
              </span>
            ))}
          </div>
        </>
      )}

      {day.notes && (
        <>
          <div className="day-section-title">Notes</div>
          <p className="voice" style={{ fontSize: "15px", paddingTop: "16px" }}>{day.notes}</p>
        </>
      )}
    </div>
  );
}
