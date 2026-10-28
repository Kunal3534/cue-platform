"use client";
import { useEffect, useState } from "react";

const PHASES = [
  "Reading the receipt…",
  "Finding the totals…",
  "Sorting the categories…",
  "Nearly there…",
];

/**
 * Animated progress indicator for receipt reading — a little document with a
 * scanning beam and rotating status copy. Pure CSS animation, no asset
 * downloads, so it works instantly on shoot-day hotel wifi.
 */
export default function ReceiptScanner({ label }: { label?: string }) {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (label) return;
    const t = setInterval(() => setPhase((p) => (p + 1) % PHASES.length), 2200);
    return () => clearInterval(t);
  }, [label]);

  return (
    <span className="gq-scan" role="status" aria-live="polite">
      <span className="gq-scan__doc" aria-hidden>
        <span className="gq-scan__line" />
        <span className="gq-scan__line gq-scan__line--short" />
        <span className="gq-scan__line" />
        <span className="gq-scan__beam" />
      </span>
      <span className="gq-scan__text" key={label ?? phase}>
        {label ?? PHASES[phase]}
      </span>
    </span>
  );
}
