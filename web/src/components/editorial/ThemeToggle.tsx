"use client";
import { useEffect, useState } from "react";

/**
 * Light/dark switch for the GQ surfaces. The choice lives on
 * <html data-gq-theme> (set pre-hydration by the inline script in the root
 * layout, so there's no flash) and persists per device in localStorage.
 * With no stored choice the OS preference applies via CSS media queries.
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
      className="gq-theme-toggle"
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
    >
      {theme === null ? "" : theme === "dark" ? "☀" : "☾"}
    </button>
  );
}
