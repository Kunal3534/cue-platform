"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getActivity } from "@/lib/api";

/** "shubhra.shukla@condenast.in" → "Shubhra Shukla" */
function displayName(email: string | null): string {
  if (!email) return "Someone";
  const stem = email.split("@")[0];
  return stem
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function fmtWhen(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const mins = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const sameDay = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  if (sameDay) return `today ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return `yesterday ${time}`;
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} ${time}`;
}

export default function ActivityPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data, isLoading } = useQuery({
    queryKey: ["activity", projectId],
    queryFn: () => getActivity(projectId),
  });

  if (isLoading || !data) {
    return <p style={{ color: "#999", padding: "40px 0" }}>Loading…</p>;
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div className="gq-detail__date">Activity</div>
      <div className="gq-detail__headline">Who changed what</div>
      <p className="gq-exp-note">
        Every edit anyone on the team makes is recorded here automatically.
      </p>

      {data.items.length === 0 ? (
        <p style={{ color: "#999", marginTop: 40, textAlign: "center" }}>
          Nothing yet — changes made from now on will appear here.
        </p>
      ) : (
        <div style={{ marginTop: 28 }}>
          {data.items.map((item) => (
            <div key={item.id} className="gq-act-row">
              <div className="gq-act-row__who">{displayName(item.user_email)}</div>
              <div className="gq-act-row__what">{item.summary}</div>
              <div className="gq-act-row__when">{fmtWhen(item.created_at)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
