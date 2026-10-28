/**
 * Editorial segment phases, keyed by the segment ref prefix (the part before
 * the dash: FIT-1 → FIT). This is the naming convention the editorial seed and
 * templates use; anything unrecognised falls back to the film D/N colouring.
 */

export interface SegmentPhase {
  key: string;
  label: string;
  stripClass: string;
  chipColor: string;
}

export const EDITORIAL_PHASES: SegmentPhase[] = [
  { key: "FIT", label: "Fittings", stripClass: "cal-strip--fit", chipColor: "#8A6FB8" },
  { key: "CVR", label: "Cover", stripClass: "cal-strip--cvr", chipColor: "#BC2F2A" },
  { key: "PRT", label: "Portfolio", stripClass: "cal-strip--prt", chipColor: "#F4CE45" },
  { key: "VID", label: "Films", stripClass: "cal-strip--vid", chipColor: "#23345C" },
  { key: "REH", label: "Rehearsal", stripClass: "cal-strip--reh", chipColor: "#A89B7E" },
  { key: "EVT", label: "Event", stripClass: "cal-strip--evt", chipColor: "#141418" },
];

const BY_KEY = new Map(EDITORIAL_PHASES.map((p) => [p.key, p]));

export function phaseForRef(sceneNumber: string): SegmentPhase | null {
  const prefix = sceneNumber.split("-")[0]?.toUpperCase() ?? "";
  return BY_KEY.get(prefix) ?? null;
}

export function dnStripClass(dn: string | null | undefined): string {
  const d = (dn ?? "").toLowerCase();
  if (d.includes("night"))
    return d.includes("int") ? "cal-strip--night-int" : "cal-strip--night";
  if (d.includes("int")) return "cal-strip--day-int";
  if (d.includes("dusk") || d.includes("dawn")) return "cal-strip--dusk";
  return "cal-strip--day";
}

export function stripClass(
  sceneNumber: string,
  dn: string | null | undefined,
  editorial: boolean,
): string {
  if (editorial) {
    const phase = phaseForRef(sceneNumber);
    if (phase) return phase.stripClass;
  }
  return dnStripClass(dn);
}
