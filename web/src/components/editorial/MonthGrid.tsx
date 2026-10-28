"use client";
import type { EditorialDay } from "@/lib/api/types";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function firstNames(day: EditorialDay): string[] {
  return day.talent.map((t) => t.name);
}

/**
 * Full-month minimal calendar. Shoot days carry the talent names and a
 * PHOTOS + FILM tag; clicking one hands the date to `onSelect`.
 */
export default function MonthGrid({
  days,
  onSelect,
  onSelectEmpty,
  selectedDate,
}: {
  days: EditorialDay[];
  onSelect?: (day: EditorialDay) => void;
  /** Producer-only: makes empty dates clickable to add a shoot. */
  onSelectEmpty?: (dateStr: string) => void;
  selectedDate?: string | null;
}) {
  const anchor = days[0] ? new Date(`${days[0].date}T00:00:00`) : new Date();
  const year = anchor.getFullYear();
  const month = anchor.getMonth(); // 0-based

  const byDate = new Map(days.map((d) => [d.date, d]));
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
    [d.location.name, d.call_time ? `Call ${d.call_time}` : null]
      .filter(Boolean)
      .join(" · ");

  return (
    <div>
      <h2 className="gq-month">
        {MONTHS[month]} {year}
      </h2>
      <div className="gq-grid-head">
        {DOW.map((d) => (
          <div key={d}>{d}</div>
        ))}
      </div>
      <div className="gq-grid">
        {cells.map((cell, i) => {
          if (!cell) return <div key={`pad-${i}`} className="gq-cell gq-cell--out" />;
          const shoot = byDate.get(cell.dateStr);
          const selected = selectedDate === cell.dateStr;
          const clickable = shoot ? !!onSelect : !!onSelectEmpty;
          return (
            <div
              key={cell.dateStr}
              className={`gq-cell${shoot ? " gq-cell--shoot" : ""}${!shoot && onSelectEmpty ? " gq-cell--addable" : ""}`}
              style={selected ? { outline: "2px solid #111", outlineOffset: "-2px" } : undefined}
              onClick={
                clickable
                  ? () => (shoot ? onSelect!(shoot) : onSelectEmpty!(cell.dateStr))
                  : undefined
              }
            >
              <div className="gq-cell__date">{cell.num}</div>
              {shoot ? (
                <>
                  <div className="gq-cell__talent">
                    {firstNames(shoot).map((n) => (
                      <div key={n}>{n}</div>
                    ))}
                  </div>
                  <span className="gq-cell__tag">Photos + Film</span>
                </>
              ) : (
                onSelectEmpty && <div className="gq-cell__plus">+ Add shoot</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Mobile agenda — the grid shrinks to dots, this carries the detail */}
      <div className="gq-agenda">
        {days.map((d) => {
          const date = new Date(`${d.date}T00:00:00`);
          return (
            <div
              key={d.date}
              className="gq-agenda__card"
              onClick={onSelect ? () => onSelect(d) : undefined}
            >
              <div className="gq-agenda__date">
                <div className="gq-agenda__num">{date.getDate()}</div>
                <div className="gq-agenda__dow">
                  {date.toLocaleDateString("en-GB", { weekday: "short" })}
                </div>
              </div>
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
        })}
      </div>
    </div>
  );
}
