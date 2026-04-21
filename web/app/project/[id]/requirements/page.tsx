"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getMainSchedule } from "@/lib/api";
import { useProjectStore } from "@/stores/project";

function dnBadgeClass(dn: string | null | undefined): string {
  const d = (dn ?? "").toLowerCase();
  if (d.includes("night")) return d.includes("int") ? "strip-badge--night-int" : "strip-badge--night";
  if (d.includes("int")) return "strip-badge--day-int";
  if (d.includes("dusk") || d.includes("dawn")) return "strip-badge--dusk";
  return "";
}

export default function RequirementsPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  if (isLoading || !data) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading requirements…</p>
      </div>
    );
  }

  const shootDays = data.days.filter((d) => d.kind === "shoot");

  return (
    <div style={{ paddingTop: "32px" }}>
      <div className="meta meta--red" style={{ marginBottom: "8px" }}>Requirements</div>
      <h2 className="display--sm" style={{ marginBottom: "32px" }}>
        Day-by-day<span className="red">.</span>
      </h2>

      {shootDays.map((day) => {
        const dn = day.scenes[0]?.dn ?? "";
        const totalEighths = day.scenes.reduce((s, sc) => s + (sc.page_eighths ?? 0), 0);

        return (
          <div key={day.day_id} className="reqday">
            <div className="reqday__ident">
              <span className={`strip-badge ${dnBadgeClass(dn)}`}>Day {day.shoot_day_number}</span>
              <div className="reqday__date">
                {new Date(day.date).toLocaleDateString("en-IN", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </div>
              {day.location && (
                <>
                  <div className="reqday__loc">{day.location.name}</div>
                  <div className="reqday__sub">{day.location.area}</div>
                </>
              )}
            </div>

            <div className="reqday__body">
              <div className="reqitem">
                <div className="reqitem__lbl">Scenes</div>
                <div className="reqitem__val">{day.scenes.map((s) => s.scene_number).join(", ") || "—"}</div>
              </div>
              <div className="reqitem">
                <div className="reqitem__lbl">Pages</div>
                <div className="reqitem__val reqitem__val--mono">{totalEighths}⅛</div>
              </div>
              <div className="reqitem">
                <div className="reqitem__lbl">Principal Cast</div>
                <div className="reqitem__val">{day.cast.join(", ") || "—"}</div>
              </div>
              <div className="reqitem">
                <div className="reqitem__lbl">Junior Artists</div>
                <div className="reqitem__val reqitem__val--mono">{day.jr_count ?? "—"}</div>
              </div>
              <div className="reqitem">
                <div className="reqitem__lbl">Shift</div>
                <div className="reqitem__val reqitem__val--mono">
                  {day.shift_start && day.shift_end
                    ? `${day.shift_start} – ${day.shift_end}`
                    : "—"}
                </div>
              </div>
              <div className="reqitem">
                <div className="reqitem__lbl">Camera Units</div>
                <div className="reqitem__val reqitem__val--mono">
                  {day.camera_units.map((u) => u.unit_code).join(", ") || "—"}
                </div>
              </div>
              {day.notes && (
                <div className="reqitem" style={{ gridColumn: "1 / -1" }}>
                  <div className="reqitem__lbl">Notes</div>
                  <div className="reqitem__val">{day.notes}</div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
