"use client";
import { useState } from "react";
import type { EditorialDay, EditorialMarker } from "@/lib/api/types";
import { fmtTime } from "@/lib/time";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function firstNames(day: EditorialDay): string[] {
  return day.talent.map((t) => t.name);
}

/**
 * Minimal month calendar with ‹ › navigation — any month, any year; shoots
 * aren't limited to the seeded window. Shoot days carry the talent names and
 * a PHOTOS + FILM tag; clicking one hands the date to `onSelect`. The agenda
 * below always lists every shoot across all months.
 */
export default function MonthGrid({
  days,
  markers = [],
  onSelect,
  onSelectEmpty,
  selectedDate,
}: {
  days: EditorialDay[];
  markers?: EditorialMarker[];
  onSelect?: (day: EditorialDay) => void;
  /** Producer-only: makes empty dates clickable to add a shoot. */
  onSelectEmpty?: (dateStr: string) => void;
  selectedDate?: string | null;
}) {
  const anchor = days[0] ? new Date(`${days[0].date}T00:00:00`) : new Date();
  const [view, setView] = useState({
    year: anchor.getFullYear(),
    month: anchor.getMonth(), // 0-based
  });
  const { year, month } = view;

  const step = (delta: number) => {
    const d = new Date(year, month + delta, 1);
    setView({ year: d.getFullYear(), month: d.getMonth() });
  };

  const byDate = new Map(days.map((d) => [d.date, d]));
  const markersByDate = new Map<string, EditorialMarker[]>();
  for (const m of markers) {
    markersByDate.set(m.date, [...(markersByDate.get(m.date) ?? []), m]);
  }
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startDow = (new Date(year, month, 1).getDay() + 6) % 7; // Mon=0

  const cells: Array<{ dateStr: string; num: number } | null> = [
    ...Array.from({ length: startDow }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => ({
      dateStr: `${year}-${String(month + 1).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`,
      num: i + 1,
    })),
  ];

  const fmtAgendaMeta = (d: EditorialDay) =>
    [d.location.name, d.call_time ? `Call ${fmtTime(d.call_time)}` : null]
      .filter(Boolean)
      .join(" · ");

  return (
    <div>
      <div className="gq-month-row">
        <button type="button" className="gq-month-nav" aria-label="Previous month" onClick={() => step(-1)}>
          ‹
        </button>
        <h2 className="gq-month" style={{ margin: 0 }}>
          {MONTHS[month]} {year}
        </h2>
        <button type="button" className="gq-month-nav" aria-label="Next month" onClick={() => step(1)}>
          ›
        </button>
      </div>
      <div className="gq-grid-head">
        {DOW.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="gq-grid">
        {cells.map((cell, i) => {
          if (!cell) return <div key={`pad-${i}`} className="gq-cell gq-cell--out" />;
          const shoot = byDate.get(cell.dateStr);
          const dayMarkers = markersByDate.get(cell.dateStr) ?? [];
          const holiday = !shoot && dayMarkers.find((m) => m.kind === "holiday");
          const personal = !shoot && !holiday && dayMarkers.find((m) => m.kind === "personal");
          const feature = holiday || personal;
          const selected = selectedDate === cell.dateStr;
          const clickable = shoot ? !!onSelect : !!onSelectEmpty;
          return (
            <div
              key={cell.dateStr}
              className={[
                "gq-cell",
                shoot ? "gq-cell--shoot" : "",
                holiday ? "gq-cell--holiday" : "",
                personal ? "gq-cell--personal" : "",
                !shoot && onSelectEmpty ? "gq-cell--addable" : "",
                selected ? "gq-cell--selected" : "",
              ].filter(Boolean).join(" ")}
              onClick={
                clickable
                  ? () => (shoot ? onSelect!(shoot) : onSelectEmpty!(cell.dateStr))
                  : undefined
              }
            >
              <div className="gq-cell__date">
                {cell.num}
                {shoot && dayMarkers.length > 0 && (
                  <span className="gq-cell__mini-emoji">{dayMarkers[0].emoji}</span>
                )}
              </div>
              {shoot ? (
                <>
                  <div className="gq-cell__talent">
                    {firstNames(shoot).map((n) => (
                      <div key={n}>{n}</div>
                    ))}
                  </div>
                  {shoot.location.name && (
                    <div className="gq-cell__loc">{shoot.location.name}</div>
                  )}
                  <span className="gq-cell__tag">Photos + Film</span>
                </>
              ) : feature ? (
                <div className="gq-marker">
                  <span className="gq-marker__emoji">{feature.emoji}</span>
                  <span className="gq-marker__label">
                    {feature.label}
                    {feature.kind === "personal" && feature.who ? ` — ${feature.who}` : ""}
                  </span>
                </div>
              ) : (
                onSelectEmpty && <div className="gq-cell__plus">+ Add</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Mobile agenda — the grid shrinks to dots, this carries the detail.
          Shoots and special days interleave chronologically. */}
      <div className="gq-agenda">
        {[
          ...days.map((d) => ({ sort: d.date, shoot: d, marker: null as EditorialMarker | null })),
          ...markers.map((m) => ({ sort: m.date, shoot: null as EditorialDay | null, marker: m })),
        ]
          .sort((a, b) => a.sort.localeCompare(b.sort))
          .map((entry) => {
            const date = new Date(`${entry.sort}T00:00:00`);
            const dateBlock = (
              <div className="gq-agenda__date">
                <div className="gq-agenda__num">{date.getDate()}</div>
                <div className="gq-agenda__dow">
                  {date.toLocaleDateString("en-GB", { month: "short" })} ·{" "}
                  {date.toLocaleDateString("en-GB", { weekday: "short" })}
                </div>
              </div>
            );
            if (entry.shoot) {
              const d = entry.shoot;
              return (
                <div
                  key={`s-${d.date}`}
                  className="gq-agenda__card"
                  onClick={onSelect ? () => onSelect(d) : undefined}
                >
                  {dateBlock}
                  <div className="gq-agenda__body">
                    <div className="gq-agenda__talent">
                      {d.talent.map((t) => t.name).join(" · ") || d.headline || "Shoot"}
                    </div>
                    <div className="gq-agenda__meta">
                      Photos + Film{fmtAgendaMeta(d) ? ` · ${fmtAgendaMeta(d)}` : ""}
                    </div>
                  </div>
                  <div className="gq-agenda__arrow">›</div>
                </div>
              );
            }
            const m = entry.marker!;
            return (
              <div
                key={`m-${m.id}`}
                className={`gq-agenda__card gq-agenda__card--${m.kind}`}
                onClick={onSelectEmpty ? () => onSelectEmpty(m.date) : undefined}
              >
                {dateBlock}
                <div className="gq-agenda__body">
                  <div className="gq-agenda__talent">
                    <span className="gq-marker__emoji">{m.emoji}</span> {m.label}
                  </div>
                  {m.kind === "personal" && m.who && (
                    <div className="gq-agenda__meta">{m.who}’s day</div>
                  )}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
