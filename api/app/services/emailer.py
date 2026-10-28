"""Branded transactional email — one frame, used by every sender.

The frame mirrors the platform: paper ground, the MOTY lockup as the
masthead, an editorial serif card, pill button, and the Cue mark in the
footer. Inline styles only (Gmail strips everything else); images are
absolute URLs on the public web app.
"""
from __future__ import annotations

import httpx

from ..config import settings

INK = "#141418"
PAPER = "#EFEDE8"
CARD = "#F7F5F0"
MUTED = "#5F5D56"
GOLD = "#8A6D1F"
HAIR = "#DDD9D0"


def _base() -> str:
    return settings.app_base_url.rstrip("/")


def button(label: str, url: str) -> str:
    return (
        f'<p style="margin:26px 0 0"><a href="{url}" '
        f'style="display:inline-block;background:{INK};color:#F3F1EC;text-decoration:none;'
        f'padding:14px 32px;border-radius:999px;font-size:13px;letter-spacing:0.12em;'
        f'text-transform:uppercase;font-family:Helvetica,Arial,sans-serif">{label}</a></p>'
    )


def kv_rows(pairs: list[tuple[str, str]]) -> str:
    """Briefing-style key/value rows, like the day page."""
    rows = ""
    for k, v in pairs:
        rows += (
            f'<tr><td style="padding:10px 18px 10px 0;color:{MUTED};font-size:10px;'
            f'letter-spacing:0.18em;text-transform:uppercase;font-family:Helvetica,Arial,sans-serif;'
            f'vertical-align:top;white-space:nowrap">{k}</td>'
            f'<td style="padding:10px 0;font-size:14.5px;color:{INK};'
            f'font-family:Georgia,serif;border-bottom:1px solid {HAIR}">{v}</td></tr>'
        )
    return (
        f'<table style="border-collapse:collapse;width:100%;margin:18px 0 0;'
        f'border-top:2px solid {INK}">{rows}</table>'
    )


def frame(eyebrow: str, headline: str, sub: str | None, body_html: str) -> str:
    base = _base()
    return f"""
<div style="background:{PAPER};padding:42px 16px;margin:0">
  <div style="max-width:540px;margin:0 auto;text-align:center">
    <img src="{base}/moty-logo.jpg" alt="GQ Men of the Year" width="132"
         style="width:132px;height:auto;margin:0 auto 26px;display:inline-block" />
  </div>
  <div style="max-width:540px;margin:0 auto;background:{CARD};
              border:1px solid #FFFFFF;border-radius:22px;padding:36px 36px 32px;
              box-shadow:0 12px 32px rgba(20,20,24,0.08)">
    <p style="letter-spacing:0.26em;font-size:11px;color:{GOLD};margin:0 0 10px;
              font-family:Helvetica,Arial,sans-serif">{eyebrow}</p>
    <h1 style="font-family:Georgia,serif;font-weight:600;font-size:28px;line-height:1.25;
               color:{INK};margin:0 0 6px">{headline}</h1>
    {f'<p style="font-size:14px;color:{MUTED};margin:0 0 20px;font-family:Georgia,serif">{sub}</p>' if sub else ''}
    <div style="font-family:Georgia,serif;color:{INK};font-size:15px;line-height:1.75">
      {body_html}
    </div>
  </div>
  <div style="max-width:540px;margin:28px auto 0;text-align:center">
    <img src="{base}/cue-logo.png" alt="Cue" width="30"
         style="width:30px;height:30px;margin:0 auto 10px;display:inline-block" />
    <p style="font-size:10px;letter-spacing:0.24em;color:#A09D95;margin:0;
              font-family:Helvetica,Arial,sans-serif">
      PRODUCED ON CUE · <a href="{base}" style="color:#A09D95;text-decoration:none">
      {base.replace('https://', '').upper()}</a></p>
  </div>
</div>"""


async def send(to: str, subject: str, html: str) -> None:
    """Deliver via Resend; silently a no-op without an API key (dev)."""
    if not settings.resend_api_key:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}",
                     "Content-Type": "application/json"},
            json={"from": settings.mail_from or "Cue <cue@cueit.io>",
                  "to": [to], "subject": subject, "html": html},
        )
