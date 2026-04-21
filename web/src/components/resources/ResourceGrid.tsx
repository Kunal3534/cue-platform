"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { listResources } from "@/lib/api";
import type { ResourceKind } from "@/lib/api";
import type { ResourceItem } from "@/lib/api/types";

interface Props {
  kind: ResourceKind;
  title: string;
  description?: string;
  columns: { key: string; label: string }[];
}

export default function ResourceGrid({ kind, title, description, columns }: Props) {
  const params = useParams();
  const projectId = params.id as string;

  const { data, isLoading, error } = useQuery({
    queryKey: ["resources", projectId, kind],
    queryFn: () => listResources(projectId, kind),
    retry: false,
  });

  if (isLoading) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading {title.toLowerCase()}…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="meta meta--red" style={{ marginBottom: "4px" }}>Resources</div>
      <h2 className="display--sm" style={{ marginBottom: "8px" }}>
        {title}<span style={{ color: "var(--cue-red)" }}>.</span>
      </h2>
      {description && (
        <p className="voice" style={{ fontSize: "15px", marginBottom: "24px" }}>
          {description}
        </p>
      )}

      {error ? (
        <div className="empty">
          <span className="empty__mark">CUE</span>
          <p className="voice" style={{ fontSize: "15px" }}>
            {title} aren&rsquo;t available yet.
          </p>
          <p className="mono-xs" style={{ color: "var(--slate-50)", marginTop: "8px" }}>
            {error instanceof Error ? error.message : String(error)}
          </p>
        </div>
      ) : !data || data.length === 0 ? (
        <div className="empty">
          <span className="empty__mark">CUE</span>
          <p className="voice" style={{ fontSize: "15px" }}>No {title.toLowerCase()} found.</p>
        </div>
      ) : (
        <div className="rgrid">
          <table className="rgrid__table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={col.key === columns[0].key ? "rgrid__corner" : "rgrid__day-head"}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((item) => (
                <tr key={item.id}>
                  {columns.map((col, i) => (
                    <td
                      key={col.key}
                      className={i === 0 ? "rgrid__row-head" : ""}
                    >
                      {formatValue(item, col.key)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatValue(item: ResourceItem, key: string): string {
  const v = item[key];
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
