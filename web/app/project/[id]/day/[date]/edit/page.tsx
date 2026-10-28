"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getEditorialSchedule,
  upsertShootDay,
  uploadMoodboard,
  moveShootDay,
  getMe,
  getPickerConfig,
  setMoodboardFromGoogle,
} from "@/lib/api";
import { openDrivePicker } from "@/lib/googlePicker";

interface TalentRow {
  name: string;
  role: string;
  call_time: string; // this talent's own call
  hmu_lead: string; // HMU artist
}

const EMPTY_TALENT: TalentRow = { name: "", role: "", call_time: "", hmu_lead: "" };

function fmtDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function EditShootDayPage() {
  const params = useParams();
  const projectId = params.id as string;
  const date = params.date as string;
  const router = useRouter();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["editorial-schedule", projectId],
    queryFn: () => getEditorialSchedule(projectId),
  });
  const existing = data?.days.find((d) => d.date === date);

  const [shootDate, setShootDate] = useState(date);
  const [talent, setTalent] = useState<TalentRow[]>([{ ...EMPTY_TALENT }]);
  const [locationName, setLocationName] = useState("");
  const [locationArea, setLocationArea] = useState("");
  const [callTime, setCallTime] = useState("");
  const [wrapTime, setWrapTime] = useState("");
  const [lightingCall, setLightingCall] = useState("");
  const [hmuCall, setHmuCall] = useState("");
  const [crewCall, setCrewCall] = useState("");
  const [photoStart, setPhotoStart] = useState("");
  const [filmStart, setFilmStart] = useState("");
  const [photographer, setPhotographer] = useState("");
  const [video, setVideo] = useState("");
  const [notes, setNotes] = useState("");
  const [moodboardLink, setMoodboardLink] = useState("");
  const [moodboardFile, setMoodboardFile] = useState<File | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [driveMsg, setDriveMsg] = useState<string | null>(null);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 60_000 });

  const pickFromDrive = async () => {
    setDriveMsg(null);
    try {
      const cfg = await getPickerConfig();
      await openDrivePicker(cfg, async (files) => {
        if (files.length === 0) return;
        try {
          await setMoodboardFromGoogle(projectId, date, files);
          await qc.invalidateQueries({ queryKey: ["editorial-schedule", projectId] });
          setDriveMsg("Moodboard set from Drive ✓");
        } catch (e) {
          setDriveMsg(e instanceof Error ? e.message : "Could not set the moodboard");
        }
      });
    } catch (e) {
      setDriveMsg(e instanceof Error ? e.message : "Could not open the Google picker");
    }
  };

  useEffect(() => {
    if (loaded || !data) return;
    if (existing) {
      setTalent(
        existing.talent.length > 0
          ? existing.talent.map((t) => ({
              name: t.name,
              role: t.role ?? "",
              call_time: t.call_time ?? t.hmu_call ?? "",
              hmu_lead: t.hmu_lead ?? "",
            }))
          : [{ ...EMPTY_TALENT }],
      );
      setLocationName(existing.location.name ?? "");
      setLocationArea(existing.location.area ?? "");
      setCallTime(existing.call_time ?? "");
      setWrapTime(existing.wrap_time ?? "");
      setLightingCall(existing.calls?.lighting ?? "");
      setHmuCall(existing.calls?.hmu ?? "");
      setCrewCall(existing.calls?.crew ?? "");
      setPhotographer(existing.photographer ?? "");
      setVideo(existing.video ?? "");
      setNotes(existing.notes ?? "");
      const photo = existing.segments.find((s) => s.ref.startsWith("P"));
      const film = existing.segments.find((s) => s.ref.startsWith("F"));
      setPhotoStart(photo?.start ?? "");
      setFilmStart(film?.start ?? "");
      if (existing.moodboard?.kind === "link") setMoodboardLink(existing.moodboard.url);
    }
    setLoaded(true);
  }, [data, existing, loaded]);

  const setTalentField = (i: number, field: keyof TalentRow, value: string) =>
    setTalent((rows) => rows.map((r, j) => (j === i ? { ...r, [field]: value } : r)));

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      // Date changed on an existing shoot → move it first, then apply edits.
      // Everything travels: talent, segments, HMU, moodboard files, todos.
      if (existing && shootDate !== date) {
        await moveShootDay(projectId, date, shootDate);
      }
      await upsertShootDay(projectId, shootDate, {
        talent: talent
          .filter((t) => t.name.trim())
          .map((t) => ({
            name: t.name.trim(),
            role: t.role.trim() || null,
            call_time: t.call_time.trim() || null,
            hmu_lead: t.hmu_lead.trim() || null,
          })),
        location_name: locationName.trim() || null,
        location_area: locationArea.trim() || null,
        call_time: callTime.trim() || null,
        wrap_time: wrapTime.trim() || null,
        lighting_call: lightingCall.trim() || null,
        hmu_call: hmuCall.trim() || null,
        crew_call: crewCall.trim() || null,
        photo_start: photoStart.trim() || null,
        film_start: filmStart.trim() || null,
        photographer: photographer.trim() || null,
        video: video.trim() || null,
        notes: notes.trim() || null,
        // Only touch the moodboard when the link field actually changed —
        // an untouched empty field must not wipe an uploaded PDF.
        moodboard_link: (() => {
          if (moodboardFile) return null;
          const initial = existing?.moodboard?.kind === "link" ? existing.moodboard.url : "";
          return moodboardLink.trim() !== initial ? moodboardLink.trim() : null;
        })(),
      });
      if (moodboardFile) {
        await uploadMoodboard(projectId, shootDate, moodboardFile);
      }
      await qc.invalidateQueries({ queryKey: ["editorial-schedule", projectId] });
      await qc.invalidateQueries({ queryKey: ["todos", projectId] });
      router.push(`/project/${projectId}/day/${shootDate}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed — try again");
      setSaving(false);
    }
  };

  return (
    <div className="gq-form">
      <div style={{ marginBottom: 24 }}>
        <Link
          href={`/project/${projectId}/calendar`}
          style={{ fontSize: 11, letterSpacing: "0.2em", textTransform: "uppercase", color: "#999" }}
        >
          ← Calendar
        </Link>
      </div>

      <div className="gq-detail__date">{existing ? "Edit shoot" : "Add shoot"}</div>
      <div className="gq-detail__headline">{fmtDate(shootDate)}</div>

      <div className="gq-form__sec">Date</div>
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Shoot date</label>
          <input
            className="gq-input"
            type="date"
            value={shootDate}
            onChange={(e) => e.target.value && setShootDate(e.target.value)}
          />
        </div>
        {existing && shootDate !== date && (
          <div style={{ alignSelf: "end", fontSize: 12, color: "#777", paddingBottom: 10 }}>
            Moving this shoot from {fmtDate(date)} — talent, times, moodboard and
            to-dos all move with it.
          </div>
        )}
      </div>

      <div className="gq-form__sec">Talent</div>
      {talent.map((t, i) => (
        <div key={i} style={{ marginBottom: 14 }}>
          <div className="gq-form__grid">
            <div>
              <label className="gq-label">Name</label>
              <input className="gq-input" value={t.name} placeholder="Talent name"
                     onChange={(e) => setTalentField(i, "name", e.target.value)} />
            </div>
            <div>
              <label className="gq-label">Title / award</label>
              <input className="gq-input" value={t.role} placeholder="e.g. Actor · Men of the Year"
                     onChange={(e) => setTalentField(i, "role", e.target.value)} />
            </div>
            <div>
              <label className="gq-label">Talent call</label>
              <input className="gq-input" type="time" value={t.call_time}
                     onChange={(e) => setTalentField(i, "call_time", e.target.value)} />
            </div>
            <div>
              <label className="gq-label">HMU artist</label>
              <input className="gq-input" value={t.hmu_lead} placeholder="Hair & makeup artist"
                     onChange={(e) => setTalentField(i, "hmu_lead", e.target.value)} />
            </div>
          </div>
          {talent.length > 1 && (
            <button
              type="button"
              className="gq-btn--ghost gq-btn"
              style={{ marginTop: 8, padding: "6px 12px", fontSize: 9 }}
              onClick={() => setTalent((rows) => rows.filter((_, j) => j !== i))}
            >
              Remove talent
            </button>
          )}
        </div>
      ))}
      <button
        type="button"
        className="gq-btn gq-btn--ghost"
        style={{ padding: "8px 16px", fontSize: 10 }}
        onClick={() => setTalent((rows) => [...rows, { ...EMPTY_TALENT }])}
      >
        + Add talent
      </button>

      <div className="gq-form__sec">Location & times</div>
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Location</label>
          <input className="gq-input" value={locationName} placeholder="Studio / venue"
                 onChange={(e) => setLocationName(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Area / city</label>
          <input className="gq-input" value={locationArea} placeholder="Neighbourhood, city"
                 onChange={(e) => setLocationArea(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Call time (on site)</label>
          <input className="gq-input" type="time" value={callTime}
                 onChange={(e) => setCallTime(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Wrap</label>
          <input className="gq-input" type="time" value={wrapTime}
                 onChange={(e) => setWrapTime(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Lighting call</label>
          <input className="gq-input" type="time" value={lightingCall}
                 onChange={(e) => setLightingCall(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">HMU call</label>
          <input className="gq-input" type="time" value={hmuCall}
                 onChange={(e) => setHmuCall(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Crew call</label>
          <input className="gq-input" type="time" value={crewCall}
                 onChange={(e) => setCrewCall(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Photos start</label>
          <input className="gq-input" type="time" value={photoStart}
                 onChange={(e) => setPhotoStart(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Film starts</label>
          <input className="gq-input" type="time" value={filmStart}
                 onChange={(e) => setFilmStart(e.target.value)} />
        </div>
      </div>

      <div className="gq-form__sec">Crew</div>
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Photographer</label>
          <input className="gq-input" value={photographer} placeholder="Photographer"
                 onChange={(e) => setPhotographer(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Film / video</label>
          <input className="gq-input" value={video} placeholder="Video director"
                 onChange={(e) => setVideo(e.target.value)} />
        </div>
      </div>

      <div className="gq-form__sec">Moodboard</div>
      <div className="gq-form__grid">
        <div>
          <label className="gq-label">Link (Google Slides etc.)</label>
          <input className="gq-input" value={moodboardLink} placeholder="https://docs.google.com/presentation/…"
                 onChange={(e) => setMoodboardLink(e.target.value)} />
        </div>
        <div>
          <label className="gq-label">Or upload PDF</label>
          <input
            className="gq-input"
            type="file"
            accept="application/pdf"
            onChange={(e) => setMoodboardFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>
      {me?.google_calendar_connected && existing && (
        <div style={{ marginTop: 12 }}>
          <button type="button" className="gq-btn gq-btn--ghost"
                  style={{ padding: "9px 16px", fontSize: 10 }}
                  onClick={pickFromDrive}>
            Choose from Google Drive — Slides, PDF or images
          </button>
          {driveMsg && (
            <span style={{ marginLeft: 12, fontSize: 12,
                           color: driveMsg.endsWith("✓") ? "#5B7A3A" : "#C33" }}>
              {driveMsg}
            </span>
          )}
        </div>
      )}
      {existing?.moodboard && (
        <p style={{ fontSize: 12, color: "#999", marginTop: 8 }}>
          Current: {existing.moodboard.kind === "pdf"
            ? `uploaded PDF${existing.moodboard.filename ? ` (${existing.moodboard.filename})` : ""}`
            : existing.moodboard.kind === "images"
              ? `${existing.moodboard.pages} image${existing.moodboard.pages === 1 ? "" : "s"} from Drive`
              : "external link"} — saving a new link or PDF replaces it; clear the link field to remove it.
        </p>
      )}

      <div className="gq-form__sec">Notes</div>
      <textarea
        className="gq-input"
        value={notes}
        placeholder="Anything the day needs — closed set, lunch, access, parking…"
        onChange={(e) => setNotes(e.target.value)}
      />

      {error && (
        <p style={{ color: "#C33", fontSize: 13, marginTop: 16 }}>{error}</p>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 32 }}>
        <button type="button" className="gq-btn" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save shoot day"}
        </button>
        <Link href={`/project/${projectId}/calendar`} className="gq-btn gq-btn--ghost"
              style={{ display: "inline-block" }}>
          Cancel
        </Link>
      </div>
    </div>
  );
}
