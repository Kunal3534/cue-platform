"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getCalendar,
  getMainSchedule,
  getEditorialSchedule,
  rescheduleScene,
  mintShareLink,
} from "@/lib/api";
import { useProjectStore } from "@/stores/project";
import { useTerms, useIsEditorial } from "@/lib/terminology";
import { stripClass, EDITORIAL_PHASES } from "@/lib/segmentKind";
import MonthGrid from "@/components/editorial/MonthGrid";
import PreviewModal from "@/components/preview-modal/PreviewModal";
import type { PreviewResponse, CalendarDay } from "@/lib/api/types";

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** "Aarav Khanna" → "Aarav K" — keeps the talent line scannable in a cell. */
function shortName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? `${parts[0]} ${parts[parts.length - 1][0]}` : parts[0];
}

function talentLine(talent: string[] | undefined, max = 3): string | null {
  if (!talent || talent.length === 0) return null;
  const shown = talent.slice(0, max).map(shortName).join(" · ");
  return talent.length > max ? `${shown} +${talent.length - max}` : shown;
}

function CalCell({
  day,
  onDrop,
  editorial,
}: {
  day: CalendarDay;
  onDrop: (sceneNumber: string, targetDate: string) => void;
  editorial?: boolean;
}) {
  const [isTarget, setIsTarget] = useState(false);
  const isOff = day.kind !== "shoot";
  // Prep/buffer days can still carry segments (fittings, rehearsals) — show them.
  const hasStrips = day.scenes.length > 0;
  const dateNum = parseInt(day.date.split("-")[2], 10);

  return (
    <div
      className={`cal-cell${isOff ? " cal-cell--off" : ""}`}
      onDragOver={(e) => {
        if (isOff) return;
        e.preventDefault();
        setIsTarget(true);
      }}
      onDragLeave={() => setIsTarget(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsTarget(false);
        const sceneNumber = e.dataTransfer.getData("scene_number");
        if (sceneNumber && !isOff) onDrop(sceneNumber, day.date);
      }}
    >
      <div className="cal-cell__head">
        <div className="cal-cell__head-left">
          {day.shoot_day_number && (
            <span className="cal-cell__day-n">D{day.shoot_day_number}</span>
          )}
          <span className="cal-cell__date">{dateNum}</span>
        </div>
      </div>

      {day.banner_text && (
        <div
          className={`cal-cell__banner${
            editorial && day.kind === "buffer" ? " cal-cell__banner--milestone" : ""
          }`}
        >
          {editorial && day.kind === "buffer" ? `⚑ ${day.banner_text}` : day.banner_text}
        </div>
      )}

      {editorial && talentLine(day.talent) ? (
        <div className="cal-cell__talent">{talentLine(day.talent)}</div>
      ) : (
        day.scene_count > 0 && (
          <div className="cal-cell__summary">
            {editorial
              ? `${day.scene_count} segment${day.scene_count === 1 ? "" : "s"}`
              : `${day.scene_count} sc · ${day.page_eighths_total ?? 0}⅛ pg`}
          </div>
        )
      )}

      {!hasStrips && isOff ? (
        <div className="cal-big-banner">
          <span className="cal-big-banner__lbl">
            {editorial && day.kind === "buffer" ? "milestone" : (day.kind ?? "off")}
          </span>
        </div>
      ) : (
        <div className={`cal-strips${isTarget ? " is-drop-target" : ""}`}>
          {day.scenes.map((sc) => (
            <div
              key={sc.scene_number}
              className={`cal-strip ${stripClass(sc.scene_number, sc.dn, !!editorial)}`}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData("scene_number", sc.scene_number);
              }}
            >
              <span className="cal-strip__num">{sc.start ?? sc.scene_number}</span>
              <span className="cal-strip__desc">{sc.title ?? ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CalendarPage() {
  const isEditorial = useIsEditorial();
  return isEditorial ? <GqCalendarPage /> : <FilmCalendarPage />;
}

function GqCalendarPage() {
  const params = useParams();
  const projectId = params.id as string;
  const router = useRouter();
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle");

  const { data, isLoading } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });

  const handleShare = async () => {
    try {
      const { token } = await mintShareLink(projectId);
      await navigator.clipboard.writeText(`${window.location.origin}/share/${token}`);
      setShareState("copied");
      setTimeout(() => setShareState("idle"), 2500);
    } catch {
      setShareState("error");
      setTimeout(() => setShareState("idle"), 2500);
    }
  };

  if (isLoading || !data) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button type="button" className="gq-share-btn" onClick={handleShare}>
          {shareState === "copied"
            ? "Link copied ✓"
            : shareState === "error"
              ? "Copy failed"
              : "Share calendar"}
        </button>
      </div>
      <MonthGrid
        days={data.days}
        onSelect={(day) => router.push(`/project/${projectId}/day/${day.date}`)}
        onSelectEmpty={(dateStr) => router.push(`/project/${projectId}/day/${dateStr}/edit`)}
      />
    </div>
  );
}

function FilmCalendarPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;
  const terms = useTerms();
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [dragError, setDragError] = useState<string | null>(null);
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle");

  const handleShare = async () => {
    try {
      const { token } = await mintShareLink(projectId);
      const url = `${window.location.origin}/share/${token}`;
      await navigator.clipboard.writeText(url);
      setShareState("copied");
      setTimeout(() => setShareState("idle"), 2500);
    } catch {
      setShareState("error");
      setTimeout(() => setShareState("idle"), 2500);
    }
  };

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "calendar", scenarioId],
    queryFn: () => getCalendar(projectId, scenarioId),
  });

  // The calendar response is deliberately lean (no scene_id, no day_id), so
  // to translate a drop into a reschedule call we cross-reference the main
  // schedule, which carries the stable ids we need.
  const { data: main } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  const { sceneIdByNumber, dayIdByDate } = useMemo(() => {
    const scene: Record<string, string> = {};
    const day: Record<string, string> = {};
    if (main) {
      for (const d of main.days) {
        day[d.date] = d.day_id;
        for (const sc of d.scenes) scene[sc.scene_number] = sc.scene_id;
      }
    }
    return { sceneIdByNumber: scene, dayIdByDate: day };
  }, [main]);

  const handleDrop = async (sceneNumber: string, targetDate: string) => {
    setDragError(null);
    const sceneId = sceneIdByNumber[sceneNumber];
    const dayId = dayIdByDate[targetDate];
    if (!sceneId || !dayId) {
      setDragError("Could not resolve scene or day id — reload and retry.");
      return;
    }
    try {
      const result = await rescheduleScene(projectId, sceneId, dayId, 1);
      setPreview(result);
    } catch (e) {
      setDragError(e instanceof Error ? e.message : "Reschedule failed");
    }
  };

  if (isLoading || !data) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading calendar…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "32px" }}>
      {dragError && (
        <div
          className="mono-xs"
          style={{
            color: "var(--cue-red)",
            marginBottom: "16px",
            padding: "8px 12px",
            background: "var(--cue-red-10)",
            border: "1px solid var(--cue-red)",
          }}
        >
          {dragError}
        </div>
      )}
      {terms.mode === "editorial" && (
        <div className="cal-legend" style={{ marginBottom: "16px" }}>
          {EDITORIAL_PHASES.map((p) => (
            <span key={p.key} className="cal-legend__item" style={{ color: "var(--slate-70)" }}>
              <span className="cal-legend__chip" style={{ background: p.chipColor }} />
              {p.label}
            </span>
          ))}
          <span className="cal-legend__item" style={{ color: "var(--slate-70)" }}>
            <span className="cal-legend__chip" style={{ background: "var(--cue-red)" }} />
            ⚑ Deadline
          </span>
        </div>
      )}

      {data.months.map((month) => {
        const firstDay = new Date(month.year, month.month - 1, 1);
        const startDow = (firstDay.getDay() + 6) % 7; // Mon=0

        return (
          <div key={`${month.year}-${month.month}`} style={{ marginBottom: "40px" }}>
            <div className="meta" style={{ marginBottom: "12px", fontSize: "13px" }}>
              {month.label}
            </div>

            <div className="cal-toolbar">
              <span className="cal-toolbar__lbl">{month.label.toUpperCase()}</span>
              <span className="cal-toolbar__spacer" />
              <span className="mono-xs">{month.days.filter((d) => d.kind === "shoot").length} {terms.shootDays}</span>
              <button
                type="button"
                className="mono-xs"
                onClick={handleShare}
                style={{
                  marginLeft: "16px",
                  cursor: "pointer",
                  background: "none",
                  border: "1px solid currentColor",
                  padding: "2px 10px",
                  color: "inherit",
                  fontFamily: "inherit",
                }}
              >
                {shareState === "copied"
                  ? "Link copied ✓"
                  : shareState === "error"
                    ? "Copy failed"
                    : "Share calendar"}
              </button>
            </div>

            <div className="cal-wrap">
              <div className="cal-head">
                {DAYS_OF_WEEK.map((d) => (
                  <div key={d} className={`cal-head__cell${d === "Sun" || d === "Sat" ? " cal-head__cell--off" : ""}`}>
                    {d}
                  </div>
                ))}
              </div>

              <div className="cal-grid">
                {Array.from({ length: startDow }).map((_, i) => (
                  <div key={`empty-${i}`} className="cal-cell cal-cell--outside" />
                ))}
                {month.days.map((day) => (
                  <CalCell
                    key={day.date}
                    day={day}
                    onDrop={handleDrop}
                    editorial={terms.mode === "editorial"}
                  />
                ))}
              </div>
            </div>
          </div>
        );
      })}

      {data.unscheduled.length > 0 && (
        <div>
          <div className="day-section-title" style={{ marginTop: "0" }}>
            {terms.unscheduled} ({data.unscheduled.length})
          </div>
          <div className="cal-unsched" style={{ marginTop: "16px", border: "var(--rule)" }}>
            <div className="cal-unsched__drop">
              {data.unscheduled.map((sc) => (
                <div
                  key={sc.scene_number}
                  className={`cal-strip ${stripClass(sc.scene_number, sc.dn, terms.mode === "editorial")}`}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData("scene_number", sc.scene_number);
                  }}
                >
                  <span className="cal-strip__num">{sc.scene_number}</span>
                  <span className="cal-strip__desc">{sc.title ?? ""}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {preview && (
        <PreviewModal
          projectId={projectId}
          preview={preview}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
