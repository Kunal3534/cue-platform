"""Google Calendar sync for shoot days.

Every team member who signed in with Google gets each shoot as an event in
their primary calendar; the project owner's copy also carries the invited
guests as attendees, so Google mails them real calendar invites.

All calls are plain REST via httpx — no Google SDK dependency.
"""
from __future__ import annotations

from datetime import date as date_cls

import httpx

from ..config import settings

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
TIMEZONE = "Asia/Kolkata"


async def access_token_for(refresh_token: str) -> str | None:
    """Refresh-token → short-lived access token. None if revoked/misconfigured."""
    if not (settings.google_client_id and settings.google_client_secret and refresh_token):
        return None
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        return None
    return resp.json().get("access_token")


def build_event_body(day: dict, share_url: str | None) -> dict:
    """One shoot day (build_schedule payload shape) → Calendar event body."""
    date_iso = day["date"]
    names = " · ".join(t["name"] for t in day.get("talent", [])) or "TBC"
    summary = f"GQ MOTY — Shoot: {names}"

    lines = []
    loc = day.get("location") or {}
    if loc.get("name"):
        lines.append(f"Location: {loc['name']}" + (f", {loc['area']}" if loc.get("area") else ""))
    if day.get("call_time"):
        lines.append(f"On-site call: {day['call_time']}")
    calls = day.get("calls") or {}
    for label, key in (("Lighting", "lighting"), ("HMU", "hmu"), ("Crew", "crew")):
        if calls.get(key):
            lines.append(f"{label} call: {calls[key]}")
    if day.get("photographer"):
        lines.append(f"Photographer: {day['photographer']}")
    if share_url:
        lines.append(f"\nDay brief: {share_url}")
    lines.append("\nSynced from Cue — gq.cueit.io")

    body: dict = {
        "summary": summary,
        "description": "\n".join(lines),
        "source": {"title": "Cue", "url": share_url or "https://gq.cueit.io"},
    }
    if loc.get("name"):
        body["location"] = loc["name"] + (f", {loc['area']}" if loc.get("area") else "")

    if day.get("call_time"):
        start = f"{date_iso}T{day['call_time']}:00"
        end = f"{date_iso}T{day['wrap_time']}:00" if day.get("wrap_time") else f"{date_iso}T23:00:00"
        body["start"] = {"dateTime": start, "timeZone": TIMEZONE}
        body["end"] = {"dateTime": end, "timeZone": TIMEZONE}
    else:
        next_day = date_cls.fromisoformat(date_iso).toordinal() + 1
        body["start"] = {"date": date_iso}
        body["end"] = {"date": date_cls.fromordinal(next_day).isoformat()}
    return body


async def upsert_event(
    access_token: str,
    body: dict,
    event_id: str | None,
    attendees: list[dict] | None = None,
    notify_attendees: bool = False,
) -> str | None:
    """Create or update an event; returns the event id (None on failure)."""
    payload = dict(body)
    if attendees is not None:
        payload["attendees"] = attendees
    params = {"sendUpdates": "all" if notify_attendees else "none"}
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        if event_id:
            resp = await client.patch(f"{_EVENTS_URL}/{event_id}", json=payload,
                                      params=params, headers=headers)
            if resp.status_code == 404:  # was deleted from Google's side — recreate
                resp = await client.post(_EVENTS_URL, json=payload, params=params, headers=headers)
        else:
            resp = await client.post(_EVENTS_URL, json=payload, params=params, headers=headers)
    if resp.status_code not in (200, 201):
        return None
    return resp.json().get("id")


async def delete_event(access_token: str, event_id: str) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        await client.delete(f"{_EVENTS_URL}/{event_id}",
                            params={"sendUpdates": "all"},
                            headers={"Authorization": f"Bearer {access_token}"})
