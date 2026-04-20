"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCalendar, rescheduleScene } from "@/lib/api";
import { useProjectStore } from "@/stores/project";
import PreviewModal from "@/components/preview-modal/PreviewModal";
import type { PreviewResponse, CalendarDay } from "@/lib/api/types";

function dnStripClass(dn: string): string {
  const d = dn.toLowerCase();
  if (d.includes("night")) return d.includes("int") ? "cal-strip--night-int" : "cal-strip--night";
  if (d.includes("int")) return "cal-strip--day-int";
  if (d.includes("dusk") || d.includes("dawn")) return "cal-strip--dusk";
  return "cal-strip--day";
}

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function CalCell({
  day,
  onDrop,
}: {
  day: CalendarDay;
  onDrop: (sceneNumber: string, targetDate: string) => void;
}) {
  const [isTarget, setIsTarget] = useState(false);
  const isOff = day.kind !== "shoot";
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
        <div className="cal-cell__banner">{day.banner_text}</div>
      )}

      {day.scene_count > 0 && (
        <div className="cal-cell__summary">
          {day.scene_count} sc · {day.page_eighths_total ?? 0}⅛ pg
        </div>
      )}

      {isOff ? (
        <div className="cal-big-banner">
          <span className="cal-big-banner__lbl">{day.kind}</span>
        </div>
      ) : (
        <div className={`cal-strips${isTarget ? " is-drop-target" : ""}`}>
          {day.scenes.map((sc) => (
            <div
              key={sc.scene_number}
              className={`cal-strip ${dnStripClass(sc.dn)}`}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData("scene_number", sc.scene_number);
              }}
            >
              <span className="cal-strip__num">{sc.scene_number}</span>
              <span className="cal-strip__desc">{sc.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CalendarPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;
  const [preview, setPreview] = useState<PreviewResponse | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "calendar", scenarioId],
    queryFn: () => getCalendar(projectId, scenarioId),
  });

  const handleDrop = async (sceneNumber: string, targetDate: string) => {
    try {
      const result = await rescheduleScene(projectId, sceneNumber, targetDate, 1);
      setPreview(result);
    } catch {
      // ignore — could show toast
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
      {data.months.map((month) => {
        const firstDay = new Date(month.year, month.month - 1, 1);
        const startDow = (firstDay.getDay() + 6) % 7; // Mon=0

        return (
          <div key={`${month.year}-${month.month}`} style={{ marginBottom: "40px" }}>
            <div className="meta" style={{ marginBottom: "12px", fontSize: "13px" }}>
              {month.label} {month.year}
            </div>

            <div className="cal-toolbar">
              <span className="cal-toolbar__lbl">{month.label.toUpperCase()} {month.year}</span>
              <span className="cal-toolbar__spacer" />
              <span className="mono-xs">{month.days.filter((d) => d.kind === "shoot").length} shoot days</span>
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
                  <CalCell key={day.date} day={day} onDrop={handleDrop} />
                ))}
              </div>
            </div>
          </div>
        );
      })}

      {data.unscheduled.length > 0 && (
        <div>
          <div className="day-section-title" style={{ marginTop: "0" }}>
            Unscheduled ({data.unscheduled.length})
          </div>
          <div className="cal-unsched" style={{ marginTop: "16px", border: "var(--rule)" }}>
            <div className="cal-unsched__drop">
              {data.unscheduled.map((sc) => (
                <div
                  key={sc.scene_number}
                  className={`cal-strip ${dnStripClass(sc.dn)}`}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData("scene_number", sc.scene_number);
                  }}
                >
                  <span className="cal-strip__num">{sc.scene_number}</span>
                  <span className="cal-strip__desc">{sc.title}</span>
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
