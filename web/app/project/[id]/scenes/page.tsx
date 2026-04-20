"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getScenesMatrix } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

export default function ScenesMatrixPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "scenes_matrix", scenarioId],
    queryFn: () => getScenesMatrix(projectId, scenarioId),
  });

  if (isLoading || !data) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading scenes matrix…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="row" style={{ marginBottom: "24px" }}>
        <div>
          <div className="meta meta--red" style={{ marginBottom: "4px" }}>Scenes Matrix</div>
          <div className="proj-head__sub">
            <span>{data.scenes.length} scenes</span>
            <span>{data.meta.day_count}D / {data.meta.night_count}N</span>
            <span>{data.meta.ext_count} Ext / {data.meta.int_count} Int</span>
          </div>
        </div>
      </div>

      <div className="scmatrix">
        <div style={{ overflowX: "auto" }}>
          <table className="scmatrix__table">
            <thead>
              <tr>
                <th className="scmatrix__corner">Scene</th>
                {data.shoot_days.map((sd) => (
                  <th key={sd.day_id} className="scmatrix__day-head">
                    D{sd.shoot_day_number}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.scenes.map((sc) => (
                <tr key={sc.scene_id}>
                  <td className="scmatrix__scene">
                    <div className="scmatrix__scene-num">{sc.scene_number}</div>
                    <div className="scmatrix__scene-desc">{sc.title}</div>
                    <div className="scmatrix__scene-meta">
                      {sc.dn}
                      {sc.page_eighths !== null && ` · ${sc.page_eighths}⅛ pg`}
                    </div>
                  </td>
                  {data.shoot_days.map((sd) => {
                    const shot = sc.day_numbers.includes(sd.shoot_day_number);
                    return (
                      <td
                        key={sd.day_id}
                        className={`scmatrix__cell${shot ? " scmatrix__cell--planned" : ""}`}
                      >
                        {shot ? sd.shoot_day_number : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
