"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getSharedCalendar, sharedMoodboardUrl, sharedMoodboardPageUrl } from "@/lib/api";
import Masthead from "@/components/editorial/Masthead";
import MonthGrid from "@/components/editorial/MonthGrid";
import DayDetail from "@/components/editorial/DayDetail";
import type { EditorialDay } from "@/lib/api/types";

export default function SharedCalendarPage() {
  const params = useParams();
  const token = params.token as string;
  const [selected, setSelected] = useState<EditorialDay | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["share", token],
    queryFn: () => getSharedCalendar(token),
  });

  if (isLoading) {
    return (
      <div className="gq-page">
        <p style={{ color: "#999", padding: "80px 0", textAlign: "center" }}>Loading…</p>
      </div>
    );
  }

  if (isError || !data || data.mode !== "editorial" || !data.schedule) {
    return (
      <div className="gq-page">
        <p style={{ color: "#999", padding: "80px 0", textAlign: "center" }}>
          This share link is invalid or has been revoked.
        </p>
      </div>
    );
  }

  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ paddingBottom: 48 }}>
        <Masthead />
        <div style={{ marginTop: 32 }}>
          <MonthGrid
            days={data.schedule}
            selectedDate={selected?.date ?? null}
            onSelect={(day) => setSelected(selected?.date === day.date ? null : day)}
          />
        </div>
        {selected && (
          <div style={{ marginTop: 48 }}>
            <DayDetail
              day={selected}
              moodboardHref={selected.moodboard ? sharedMoodboardUrl(token, selected.date) : null}
              moodboardPageHref={(page) => sharedMoodboardPageUrl(token, selected.date, page)}
            />
          </div>
        )}
        <div className="gq-foot">Produced on Cue · read-only calendar</div>
      </div>
    </div>
  );
}
