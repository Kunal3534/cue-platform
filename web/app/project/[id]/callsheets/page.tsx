"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listCallSheets, getMainSchedule } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

export default function CallSheetsPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data: sheets, isLoading } = useQuery({
    queryKey: ["callsheets", projectId],
    queryFn: () => listCallSheets(projectId),
  });

  // Call sheet rows reference a day by id. We enrich with dates/shoot_day #
  // by joining against the main schedule view.
  const { data: main } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  const dayById = new Map(
    (main?.days ?? []).map((d) => [d.day_id, d] as const),
  );

  if (isLoading || !sheets) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading call sheets…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="meta meta--red" style={{ marginBottom: "8px" }}>Call Sheets</div>
      <h2 className="display--sm" style={{ marginBottom: "24px" }}>
        {sheets.length} sheet{sheets.length !== 1 ? "s" : ""}<span className="red">.</span>
      </h2>

      {sheets.length === 0 ? (
        <div className="empty">
          <span className="empty__mark">CUE</span>
          <p className="voice" style={{ fontSize: "15px" }}>
            No call sheets generated yet.
          </p>
        </div>
      ) : (
        <div className="cslist">
          {sheets.map((cs) => {
            const day = dayById.get(cs.day_id);
            const dateLabel = day
              ? new Date(day.date).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                })
              : cs.day_id.slice(0, 8);
            const dayNum = day?.shoot_day_number ?? "?";
            const loc = day?.location?.name ?? "—";
            return (
              <Link
                key={cs.id}
                href={`/project/${projectId}/callsheets/${cs.id}`}
                style={{ textDecoration: "none", display: "block" }}
              >
                <div className="cs-row">
                  <div className="cs-row__day">D{dayNum}</div>
                  <div className="cs-row__date">{dateLabel}</div>
                  <div className="cs-row__loc">{loc}</div>
                  <div className="cs-row__cast">v{cs.version}</div>
                  <div className="cs-row__time">
                    {cs.sent_at ? "sent" : cs.status}
                  </div>
                  <span className="btn btn--sm btn--ghost">View →</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
