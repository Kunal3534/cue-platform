"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, useCallback, useMemo, useRef } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  ColDef,
  CellStyle,
  CellValueChangedEvent,
  GridReadyEvent,
  GetRowIdParams,
} from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import { getMainSchedule, previewEdits } from "@/lib/api";
import { useProjectStore } from "@/stores/project";
import PreviewModal from "@/components/preview-modal/PreviewModal";
import type { PreviewResponse, EditItem } from "@/lib/api/types";

interface MasterRow {
  rowId: string;
  entityType: "scene" | "day";
  entityId: string;
  shootDay: number | null;
  date: string;
  sceneNumber: string;
  title: string | null;
  dn: string | null;
  pageEighths: number | null;
  setups: number | null;
  locationName: string;
  shiftStart: string;
  shiftEnd: string;
  cast: string;
}

type PendingPatch = {
  entityType: "scene" | "day";
  entityId: string;
  field: string;
  newValue: unknown;
};

export default function MasterPage() {
  const params = useParams();
  const projectId = params.id as string;
  const scenarioId = useProjectStore((s) => s.activeScenarioId) ?? undefined;
  const gridRef = useRef<AgGridReact<MasterRow>>(null);

  const [patches, setPatches] = useState<Map<string, PendingPatch>>(new Map());
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["view", projectId, "main_schedule", scenarioId],
    queryFn: () => getMainSchedule(projectId, scenarioId),
  });

  const rows = useMemo<MasterRow[]>(() => {
    if (!data) return [];
    const result: MasterRow[] = [];
    for (const day of data.days) {
      if (day.kind !== "shoot") continue;
      for (const sc of day.scenes) {
        result.push({
          rowId: `${day.day_id}__${sc.scene_id}`,
          entityType: "scene",
          entityId: sc.scene_id,
          shootDay: day.shoot_day_number,
          date: new Date(day.date).toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
          }),
          sceneNumber: sc.scene_number,
          title: sc.title,
          dn: sc.dn,
          pageEighths: sc.page_eighths,
          setups: sc.setups_est,
          locationName: day.location?.name ?? "",
          shiftStart: day.shift_start ?? "",
          shiftEnd: day.shift_end ?? "",
          cast: day.cast.join(", "),
        });
      }
    }
    return result;
  }, [data]);

  const colDefs = useMemo<ColDef<MasterRow>[]>(
    () => [
      {
        field: "shootDay",
        headerName: "Day",
        width: 64,
        pinned: "left",
        editable: false,
        cellStyle: {
          fontFamily: "var(--font-strip, 'Big Shoulders Display')",
          fontWeight: 800,
          fontSize: "18px",
          color: "var(--cue-red, #BC2F2A)",
        } as CellStyle,
      },
      {
        field: "sceneNumber",
        headerName: "Scene #",
        width: 80,
        pinned: "left",
        editable: false,
        cellStyle: {
          fontFamily: "var(--font-strip, 'Big Shoulders Display')",
          fontWeight: 700,
          color: "var(--cue-red, #BC2F2A)",
        } as CellStyle,
      },
      {
        field: "title",
        headerName: "Title",
        flex: 2,
        pinned: "left",
        editable: true,
        cellStyle: { fontFamily: "var(--font-serif, 'IBM Plex Serif')" } as CellStyle,
      },
      { field: "date", headerName: "Date", width: 90, editable: false },
      { field: "dn", headerName: "D/N", width: 100, editable: false },
      {
        field: "pageEighths",
        headerName: "Pages (⅛)",
        width: 100,
        editable: true,
        valueFormatter: ({ value }) =>
          value === null || value === undefined ? "—" : String(value),
      },
      { field: "setups", headerName: "Setups", width: 80, editable: false },
      {
        field: "locationName",
        headerName: "Location",
        flex: 1,
        editable: false,
        cellStyle: { fontFamily: "var(--font-serif, 'IBM Plex Serif')" } as CellStyle,
      },
      { field: "shiftStart", headerName: "Call", width: 90, editable: true },
      { field: "shiftEnd", headerName: "Wrap", width: 90, editable: true },
      {
        field: "cast",
        headerName: "Cast",
        flex: 1,
        editable: false,
        cellStyle: {
          fontFamily: "var(--font-serif, 'IBM Plex Serif')",
          fontStyle: "italic",
          fontSize: "13px",
          color: "var(--slate-70, #141418B3)",
        } as CellStyle,
      },
    ],
    [],
  );

  const defaultColDef = useMemo<ColDef<MasterRow>>(
    () => ({
      sortable: true,
      resizable: true,
      suppressHeaderMenuButton: true,
      cellStyle: { fontFamily: "var(--font-mono, 'IBM Plex Mono')", fontSize: "12px" } as CellStyle,
    }),
    [],
  );

  const onCellValueChanged = useCallback(
    (e: CellValueChangedEvent<MasterRow>) => {
      const row = e.data;
      const field = e.colDef.field as string;

      // Map grid column → entity type + DB field
      let entityType: "scene" | "day" = "scene";
      let entityId = row.entityId;
      let dbField = field;

      if (field === "shiftStart" || field === "shiftEnd") {
        // find the day entity id from data
        const dayRow = data?.days.find(
          (d) =>
            d.shoot_day_number === row.shootDay && d.kind === "shoot",
        );
        if (!dayRow) return;
        entityType = "day";
        entityId = dayRow.day_id;
        dbField = field === "shiftStart" ? "shift_start" : "shift_end";
      } else if (field === "title") {
        dbField = "title";
      } else if (field === "pageEighths") {
        dbField = "page_eighths";
      } else {
        return; // not an editable DB field
      }

      const key = `${entityType}:${entityId}:${dbField}`;
      setPatches((prev) => {
        const next = new Map(prev);
        next.set(key, { entityType, entityId, field: dbField, newValue: e.newValue });
        return next;
      });
    },
    [data],
  );

  const handlePreview = async () => {
    if (patches.size === 0) return;
    setPreviewing(true);
    try {
      const edits: EditItem[] = Array.from(patches.values()).map((p) => ({
        op: "patch",
        entity: p.entityType === "scene" ? "scenes" : "days",
        id: p.entityId,
        fields: { [p.field]: p.newValue },
      }));
      const result = await previewEdits(projectId, edits, scenarioId);
      setPreview(result);
    } finally {
      setPreviewing(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: "48px 0" }}>
        <p className="voice">Loading master breakdown…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: "0" }}>
      {patches.size > 0 && (
        <div className="mgrid__banner">
          <span>
            <strong>{patches.size}</strong> pending edit
            {patches.size !== 1 ? "s" : ""}
          </span>
          <div style={{ display: "flex", gap: "12px" }}>
            <button
              className="btn btn--sm"
              style={{
                background: "rgba(244,238,223,0.15)",
                color: "var(--chalk)",
                border: "1px solid rgba(244,238,223,0.3)",
              }}
              onClick={() => setPatches(new Map())}
            >
              Discard all
            </button>
            <button
              className="btn btn--day btn--sm"
              onClick={handlePreview}
              disabled={previewing}
            >
              {previewing ? "Previewing…" : "Preview changes →"}
            </button>
          </div>
        </div>
      )}

      <div
        className="ag-theme-alpine"
        style={{
          height: "calc(100vh - 180px)",
          width: "100%",
          "--ag-background-color": "var(--paper, #FAF5E6)",
          "--ag-odd-row-background-color": "var(--chalk, #F4EEDF)",
          "--ag-header-background-color": "var(--slate, #141418)",
          "--ag-header-foreground-color": "var(--chalk, #F4EEDF)",
          "--ag-header-column-separator-color": "rgba(244,238,223,0.15)",
          "--ag-font-family": "var(--font-mono, 'IBM Plex Mono')",
          "--ag-font-size": "12px",
          "--ag-cell-horizontal-padding": "12px",
          "--ag-border-color": "var(--hair, #D0C9BA)",
          "--ag-row-border-color": "var(--hair-soft, #E5DFD0)",
          "--ag-selected-row-background-color": "rgba(244, 206, 69, 0.18)",
          "--ag-range-selection-border-color": "var(--cue-red, #BC2F2A)",
          "--ag-range-selection-background-color": "rgba(188, 47, 42, 0.06)",
        } as React.CSSProperties}
      >
        <AgGridReact<MasterRow>
          ref={gridRef}
          rowData={rows}
          columnDefs={colDefs}
          defaultColDef={defaultColDef}
          getRowId={(p: GetRowIdParams<MasterRow>) => p.data.rowId}
          onCellValueChanged={onCellValueChanged}
          enableRangeSelection
          suppressRowClickSelection
          animateRows={false}
          rowSelection="multiple"
          headerHeight={40}
          rowHeight={42}
        />
      </div>

      {preview && (
        <PreviewModal
          projectId={projectId}
          preview={preview}
          onClose={() => setPreview(null)}
          onCommitted={() => setPatches(new Map())}
        />
      )}
    </div>
  );
}
