"use client";
import type { EditorialDay } from "@/lib/api/types";

function fmtDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** Google Slides links have an /embed form made for iframes. */
function slidesEmbedUrl(url: string): string | null {
  const m = url.match(/docs\.google\.com\/presentation\/d\/([\w-]+)/);
  return m ? `https://docs.google.com/presentation/d/${m[1]}/embed` : null;
}

/**
 * Everything one shoot day needs, nothing more: talent, location,
 * call times, photographer, HMU.
 */
export default function DayDetail({
  day,
  moodboardHref,
  moodboardPageHref,
}: {
  day: EditorialDay;
  /** Where "Open moodboard" points — computed by the parent (app vs share link). */
  moodboardHref?: string | null;
  /** URL builder for a rasterized PDF page — context-specific like moodboardHref. */
  moodboardPageHref?: (page: number) => string;
}) {
  return (
    <div className="gq-detail">
      <div className="gq-detail__date">{fmtDate(day.date)}</div>
      {day.headline && <div className="gq-detail__headline">{day.headline}</div>}

      <div className="gq-kv">
        <div className="gq-kv__row">
          <div className="gq-kv__k">Talent</div>
          <div className="gq-kv__v">
            {day.talent.map((t) => {
              const call = t.call_time ?? t.hmu_call;
              return (
                <div key={t.name} style={{ marginBottom: 6 }}>
                  <strong>{t.name}</strong>
                  {t.role && <div className="gq-kv__sub">{t.role}</div>}
                  {call && <div className="gq-kv__sub">Call {call}</div>}
                </div>
              );
            })}
          </div>
        </div>

        <div className="gq-kv__row">
          <div className="gq-kv__k">Location</div>
          <div className="gq-kv__v">
            {day.location.name ?? "TBC"}
            {day.location.area && <div className="gq-kv__sub">{day.location.area}</div>}
          </div>
        </div>

        <div className="gq-kv__row">
          <div className="gq-kv__k">Call times</div>
          <div className="gq-kv__v">
            {day.call_time && <div>On site {day.call_time}</div>}
            {day.calls?.lighting && <div>Lighting {day.calls.lighting}</div>}
            {day.calls?.hmu && <div>HMU {day.calls.hmu}</div>}
            {day.calls?.crew && <div>Crew {day.calls.crew}</div>}
            {day.segments
              .filter((s) => s.start)
              .map((s) => (
                <div key={s.ref}>
                  {s.start} — {s.title}
                </div>
              ))}
            {day.wrap_time && <div className="gq-kv__sub">Wrap {day.wrap_time}</div>}
          </div>
        </div>

        <div className="gq-kv__row">
          <div className="gq-kv__k">Photographer</div>
          <div className="gq-kv__v">
            {day.photographer ?? "TBC"}
            {day.video && <div className="gq-kv__sub">Film · {day.video}</div>}
          </div>
        </div>

        <div className="gq-kv__row">
          <div className="gq-kv__k">HMU</div>
          <div className="gq-kv__v">
            {day.talent.some((t) => t.hmu_lead)
              ? day.talent.map(
                  (t) =>
                    t.hmu_lead && (
                      <div key={t.name}>
                        {t.hmu_lead}
                        {day.talent.length > 1 && (
                          <span className="gq-kv__sub"> ({t.name})</span>
                        )}
                      </div>
                    ),
                )
              : "TBC"}
          </div>
        </div>

        {day.notes && (
          <div className="gq-kv__row">
            <div className="gq-kv__k">Notes</div>
            <div className="gq-kv__v" style={{ whiteSpace: "pre-wrap" }}>{day.notes}</div>
          </div>
        )}
      </div>

      {day.moodboard && moodboardHref && (
        <div style={{ marginTop: 44 }}>
          <div className="gq-moodboard__head">
            <span>Moodboard</span>
            <a href={moodboardHref} target="_blank" rel="noreferrer">
              Open in new tab ↗
            </a>
          </div>
          {day.moodboard.kind === "pdf" ? (
            day.moodboard.pages > 0 && moodboardPageHref ? (
              <div>
                {Array.from({ length: day.moodboard.pages }, (_, i) => (
                  <img
                    key={i}
                    src={moodboardPageHref(i + 1)}
                    alt={`Moodboard page ${i + 1}`}
                    className="gq-moodboard__page"
                    loading={i > 0 ? "lazy" : undefined}
                  />
                ))}
              </div>
            ) : (
              <a href={moodboardHref} target="_blank" rel="noreferrer" className="gq-moodboard__fallback">
                Open the moodboard PDF ↗
              </a>
            )
          ) : (() => {
            const embedSrc = slidesEmbedUrl(day.moodboard.url);
            return embedSrc ? (
              <iframe src={embedSrc} title="Moodboard" className="gq-moodboard__frame" allowFullScreen />
            ) : (
              <a href={moodboardHref} target="_blank" rel="noreferrer" className="gq-moodboard__fallback">
                This moodboard link can’t be previewed inline — open it ↗
              </a>
            );
          })()}
        </div>
      )}
    </div>
  );
}
