"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMyNote, saveMyNote } from "@/lib/api";

/** Private per-user notes on a shoot day — nobody else ever sees these. */
export default function MyDayNotes({
  projectId,
  date,
}: {
  projectId: string;
  date: string;
}) {
  const { data } = useQuery({
    queryKey: ["my-note", projectId, date],
    queryFn: () => getMyNote(projectId, date),
  });
  const [text, setText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    if (!loaded && data) {
      setText(data.text);
      setLoaded(true);
    }
  }, [data, loaded]);

  if (!data) return null;

  const save = async () => {
    setState("saving");
    try {
      await saveMyNote(projectId, date, text);
      setState("saved");
      setTimeout(() => setState("idle"), 2000);
    } catch {
      setState("error");
    }
  };

  return (
    <div style={{ marginTop: 44 }}>
      <div className="gq-moodboard__head">
        <span>My notes</span>
        <span style={{ color: "#BBB", textTransform: "none", letterSpacing: "0.04em" }}>
          only you can see these
        </span>
      </div>
      <textarea
        className="gq-input"
        value={text}
        placeholder="Your own notes for this day — looks to prep, kit to carry, timings…"
        onChange={(e) => setText(e.target.value)}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
        <button type="button" className="gq-btn" onClick={save}
                disabled={state === "saving"}
                style={{ padding: "10px 22px", fontSize: 10 }}>
          {state === "saving" ? "Saving…" : "Save notes"}
        </button>
        {state === "saved" && <span style={{ fontSize: 12, color: "#5B7A3A" }}>Saved ✓</span>}
        {state === "error" && <span style={{ fontSize: 12, color: "#C33" }}>Could not save</span>}
      </div>
    </div>
  );
}
