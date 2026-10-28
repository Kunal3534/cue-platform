"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  getSharedDay,
  sharedDayMoodboardUrl,
  sharedDayMoodboardPageUrl,
} from "@/lib/api";
import Masthead from "@/components/editorial/Masthead";
import DayDetail from "@/components/editorial/DayDetail";

export default function SharedDayPage() {
  const params = useParams();
  const token = params.token as string;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["share-day", token],
    queryFn: () => getSharedDay(token),
  });

  if (isLoading) {
    return (
      <div className="gq-page">
        <p style={{ color: "#999", padding: "80px 0", textAlign: "center" }}>Loading…</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="gq-page">
        <p style={{ color: "#999", padding: "80px 0", textAlign: "center" }}>
          This link is invalid, or the shoot has been removed.
        </p>
      </div>
    );
  }

  return (
    <div className="gq-page">
      <div className="gq-inner" style={{ paddingBottom: 48 }}>
        <Masthead />
        <div style={{ marginTop: 32 }}>
          <DayDetail
            day={data.day}
            moodboardHref={data.day.moodboard ? sharedDayMoodboardUrl(token) : null}
            moodboardPageHref={(page) => sharedDayMoodboardPageUrl(token, page)}
          />
        </div>
        <div className="gq-foot">Produced on Cue · read-only day briefing</div>
      </div>
    </div>
  );
}
