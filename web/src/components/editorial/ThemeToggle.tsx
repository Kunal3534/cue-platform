"use client";
import { useEffect, useState } from "react";

/**
 * Animated day/night switch for the GQ surfaces: a sliding knob whose sun
 * sets into a crescent moon while stars come out on the track. The choice
 * lives on <html data-gq-theme> (set pre-hydration by the inline script in
 * the root layout, so there's no flash) and persists per device.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("gq-theme");
    } catch {
      /* private mode etc. — fall through to OS preference */
    }
    if (stored === "light" || stored === "dark") setTheme(stored);
    else setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.gqTheme = next;
    try {
      localStorage.setItem("gq-theme", next);
    } catch {
      /* fine — the choice just won't survive a reload */
    }
  };

  return (
    <button
      type="button"
      className={`gq-switch${theme === "dark" ? " is-dark" : ""}`}
      role="switch"
      aria-checked={theme === "dark"}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
    >
      <span className="gq-switch__star gq-switch__star--1" aria-hidden>✦</span>
      <span className="gq-switch__star gq-switch__star--2" aria-hidden>✧</span>
      <span className="gq-switch__star gq-switch__star--3" aria-hidden>✦</span>
      <span className="gq-switch__knob" aria-hidden>
        <span className="gq-switch__sun" />
        <span className="gq-switch__moon" />
      </span>
    </button>
  );
}
