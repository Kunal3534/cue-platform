/** The Cue wordmark — a single DAY-yellow stripboard strip, pinned + tilted. */
export default function WordmarkStrip({
  label = "CUE",
  width = 160,
  tilt = -7,
}: { label?: string; width?: number; tilt?: number }) {
  const h = Math.round(width * 0.28);
  const cut = Math.round(h * Math.tan((14 * Math.PI) / 180));
  const pinR = h * 0.08;
  const fontPx = Math.round(h * 0.55);

  return (
    <span
      className="relative inline-block align-middle"
      style={{ width, height: h, transform: `rotate(${tilt}deg)` }}
      aria-label="cue"
    >
      <svg width={width} height={h} viewBox={`0 0 ${width} ${h}`}>
        <polygon
          points={`0,0 ${width - cut},0 ${width},${h} 0,${h}`}
          fill="#F4CE45"
        />
      </svg>
      <span
        className="absolute rounded-full bg-chalk"
        style={{ left: h * 0.24 - pinR, top: h / 2 - pinR, width: pinR * 2, height: pinR * 2 }}
      />
      <span
        className="absolute font-strip text-slate leading-none"
        style={{ left: h * 0.52, top: h * 0.18, fontSize: fontPx }}
      >
        {label}
      </span>
    </span>
  );
}
