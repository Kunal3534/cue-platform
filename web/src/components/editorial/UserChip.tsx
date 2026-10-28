"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMe, signOut, googleLoginUrl } from "@/lib/api";

function prettyName(name: string | null, email: string): string {
  const raw = name && !name.includes("@") ? name : email.split("@")[0];
  return raw
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

/** Signed-in user indicator — initials coin + a small glass menu with the
 *  Google Calendar connection state and sign-out. */
export default function UserChip() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 60_000 });
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!me) return null;
  const display = prettyName(me.name, me.email);
  const initials = display
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("");

  return (
    <div className="gq2-user" ref={ref}>
      <button type="button" className="gq2-user__chip" onClick={() => setOpen((o) => !o)}>
        <span className="gq2-user__avatar">{initials}</span>
        <span className="gq2-user__name">{display}</span>
      </button>
      {open && (
        <div className="gq2-user__menu">
          <div className="gq2-user__email">{me.email}</div>
          <div className="gq2-user__sep" />
          {me.google_calendar_connected ? (
            <div className="gq2-user__row gq2-user__row--ok">✓ Google Calendar synced</div>
          ) : (
            <a className="gq2-user__row" href={googleLoginUrl()}>
              Connect Google Calendar
            </a>
          )}
          <div className="gq2-user__sep" />
          <button
            type="button"
            className="gq2-user__row"
            onClick={async () => {
              await signOut();
              window.location.href = "/login";
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
