"use client";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  getMainSchedule,
  getEditorialSchedule,
  deleteShootDay,
  moodboardUrl,
  moodboardPageUrl,
} from "@/lib/api";
import { useProjectStore } from "@/stores/project";
import { useIsEditorial } from "@/lib/terminology";
import DayDetail from "@/components/editorial/DayDetail";
import DayTodos from "@/components/editorial/DayTodos";

function dnStripClass(dn: string | null | undefined): string {
  const d = (dn ?? "").toLowerCase();
  if (d.includes("night")) return "scene-strip__dn--night";
  if (d.includes("dusk") || d.includes("dawn")) return "scene-strip__dn--dusk";
  return "";
}

export default function DayDetailPage() {
  const isEditorial = useIsEditorial();
  return isEditorial ? <GqDayPage /> : <FilmDayPage />;
}

function GqDayPage() {
  const params = useParams();
  const projectId = params.id as string;
  const date = params.date as string;
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });

  const day = data?.days.find((d) => d.date === date);

  const handleDelete = async () => {
    if (!window.confirm("Remove this shoot day? The date stays on the calendar as an empty day.")) return;
    await deleteShootDay(projectId, date);
    await qc.invalidateQueries({ queryKey: ["editorial-schedule", projectId] });
    router.push(`/project/${projectId}/calendar`);
  };

  if (isLoading) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  if (!day) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <p style={{ color: "#999" }}>No shoot on this date.</p>
        <Link
          href={`/project/${projectId}/day/${date}/edit`}
          className="gq-btn"
          style={{ display: "inline-block", marginTop: 16 }}
        >
          Add a shoot here
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Link href={`/project/${projectId}/calendar`} style={{ fontSize: 11, letterSpacing: "0.2em", textTransform: "uppercase", color: "#999" }}>
          ← Calendar
        </Link>
        <div style={{ display: "flex", gap: 10 }}>
          <Link
            href={`/project/${projectId}/day/${date}/edit`}
            className="gq-btn gq-btn--ghost"
            style={{ padding: "8px 18px", fontSize: 10 }}
          >
            Edit
          </Link>
          <button
            type="button"
            className="gq-btn gq-btn--danger"
            style={{ padding: "8px 18px", fontSize: 10 }}
            onClick={handleDelete}
          >
            Delete
          </button>
        </div>
      </div>
      <DayDetail
        day={day}
        moodboardHref={day.moodboard ? moodboardUrl(projectId, date) : null}
        moodboardPageHref={(page) => moodboardPageUrl(projectId, date, page)}
      />
      <div className="gq-detail">
        <DayTodos projectId={projectId} date={date} />
      </div>
    </div>
  );
}

function FilmDayPage() {
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
          {(day.jr_count ?? 0) > 0 && (
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
            <div className="scene-strip__pages-sub">{sc.setups_est ?? 0} setups</div>
          </div>
          <div>
            <span className={`scene-strip__dn ${dnStripClass(sc.dn)}`}>{sc.dn ?? ""}</span>
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
            {(day.jr_count ?? 0) > 0 && (
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
