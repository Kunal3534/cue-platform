"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getCastDood } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

type StatusCell = "W" | "H" | "T" | ".";

function cellClass(v: StatusCell): string {
  return `dood__cell dood__cell--${v}`;
}

function computeSummary(days: Record<string, string>): { W: number; H: number; T: number } {
  let W = 0, H = 0, T = 0;
  for (const v of Object.values(days)) {
    if (v === "W") W += 1;
    else if (v === "H") H += 1;
    else if (v === "T") T += 1;
  }
  return { W, H, T };
}

export default function CastDoodPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "cast_dood", scenarioId],
    queryFn: () => getCastDood(projectId, scenarioId),
  });

  if (isLoading || !data) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading cast DOOD…</p>
      </div>
    );
  }

  const principals = data.characters.filter((c) => c.is_principal);
  const supporting = data.characters.filter((c) => !c.is_principal);

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="row" style={{ marginBottom: "24px" }}>
        <div>
          <div className="meta meta--red" style={{ marginBottom: "4px" }}>Cast DOOD</div>
          <div className="proj-head__sub">
            <span>{data.characters.length} characters</span>
            <span>{data.shoot_days.length} shoot days</span>
          </div>
        </div>
      </div>

      <div className="dood">
        <table className="dood__table">
          <thead>
            <tr>
              <th className="dood__corner">Character / Actor</th>
              {data.shoot_days.map((sd) => (
                <th key={sd.day_id} className="dood__day-head">
                  {sd.shoot_day_number}
                </th>
              ))}
              <th className="dood__day-head" style={{ background: "var(--slate-70)" }}>W</th>
              <th className="dood__day-head" style={{ background: "var(--slate-70)" }}>H</th>
              <th className="dood__day-head" style={{ background: "var(--slate-70)" }}>T</th>
            </tr>
          </thead>
          <tbody>
            {[...principals, ...supporting].map((char) => {
              const summary = char.summary ?? computeSummary(char.days);
              return (
                <tr key={char.character_id}>
                  <td className="dood__actor">
                    <div className="dood__actor-char">{char.canonical_name}</div>
                    <div className="dood__actor-name">{char.actor_name ?? ""}</div>
                  </td>
                  {data.shoot_days.map((sd) => {
                    const v = (char.days[String(sd.shoot_day_number)] ?? ".") as StatusCell;
                    return (
                      <td key={sd.day_id} className={cellClass(v)}>
                        {v === "." ? "" : v}
                      </td>
                    );
                  })}
                  <td className="dood__cell" style={{ background: "var(--cue-red-10)", color: "var(--cue-red)" }}>
                    {summary.W}
                  </td>
                  <td className="dood__cell" style={{ background: "var(--day-int)" }}>
                    {summary.H}
                  </td>
                  <td className="dood__cell" style={{ background: "#F2DDBF" }}>
                    {summary.T}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="dood__footer">
            <tr>
              <th className="dood__corner" style={{ fontSize: "10px" }}>Day totals</th>
              {data.shoot_days.map((sd) => (
                <td key={sd.day_id} style={{ padding: "10px 6px" }}>
                  {data.day_totals[String(sd.shoot_day_number)] ?? 0}
                </td>
              ))}
              <td colSpan={3} />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
