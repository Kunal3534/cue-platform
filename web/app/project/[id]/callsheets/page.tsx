"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listCallSheets } from "@/lib/api";

export default function CallSheetsPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data, isLoading } = useQuery({
    queryKey: ["callsheets", projectId],
    queryFn: () => listCallSheets(projectId),
  });

  if (isLoading || !data) {
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
        {data.length} sheets<span className="red">.</span>
      </h2>

      {data.length === 0 ? (
        <div className="empty">
          <span className="empty__mark">CUE</span>
          <p className="voice" style={{ fontSize: "15px" }}>
            No call sheets generated yet.
          </p>
        </div>
      ) : (
        <div className="cslist">
          {data.map((cs) => (
            <Link
              key={cs.id}
              href={`/project/${projectId}/callsheets/${cs.date}`}
              style={{ textDecoration: "none", display: "block" }}
            >
              <div className="cs-row">
                <div className="cs-row__day">D{cs.shoot_day_number}</div>
                <div className="cs-row__date">
                  {new Date(cs.date).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                  })}
                </div>
                <div className="cs-row__loc">—</div>
                <div className="cs-row__cast">—</div>
                <div className="cs-row__time">—</div>
                <span className="btn btn--sm btn--ghost">View →</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
