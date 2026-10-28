/** "07:00" → "7 am" · "14:30" → "2:30 pm" — editorial-style 12-hour display.
 *  Storage and the API stay 24-hour "HH:MM"; this is display-only. */
export function fmtTime(hhmm: string | null | undefined): string | null {
  if (!hhmm) return null;
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim());
  if (!m) return hhmm;
  let h = parseInt(m[1], 10);
  if (h > 23) return hhmm;
  const ap = h >= 12 ? "pm" : "am";
  h = h % 12 || 12;
  return m[2] === "00" ? `${h} ${ap}` : `${h}:${m[2]} ${ap}`;
}
