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
<div style="background:{PAPER};padding:26px 14px 30px;margin:0">
  <div style="max-width:560px;margin:0 auto">

    <table style="width:100%;border-collapse:collapse;margin:0 0 16px">
      <tr>
        <td style="font-family:Helvetica,Arial,sans-serif;font-size:14px;
                   letter-spacing:0.3em;color:{INK};font-weight:bold">CUE</td>
        <td style="text-align:right;font-family:Helvetica,Arial,sans-serif;font-size:11px;
                   letter-spacing:0.12em">
          <a href="{base}" style="color:{MUTED};text-decoration:none">GQ.CUEIT.IO</a></td>
      </tr>
    </table>

    <div style="background:#FBFAF6;border-radius:20px;overflow:hidden;
                border:1px solid #FFFFFF;box-shadow:0 12px 32px rgba(20,20,24,0.10)">
      <img src="{base}/email-hero.jpg" alt="GQ Men of the Year" width="560"
           style="width:100%;height:auto;display:block" />
      <div style="padding:34px 38px 34px">
        <p style="letter-spacing:0.24em;font-size:10.5px;color:{GOLD};margin:0 0 10px;
                  font-family:Helvetica,Arial,sans-serif">{eyebrow}</p>
        <h1 style="font-family:Georgia,serif;font-weight:600;font-size:28px;line-height:1.25;
                   color:{INK};margin:0 0 6px">{headline}</h1>
        {f'<p style="font-size:14px;color:{MUTED};margin:0 0 6px;font-family:Georgia,serif">{sub}</p>' if sub else ''}
        <div style="font-family:Georgia,serif;color:{INK};font-size:15px;line-height:1.7">
          {body_html}
        </div>
      </div>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:26px 0 0">
      <tr><td style="text-align:center;font-family:Helvetica,Arial,sans-serif;
                     font-size:11px;letter-spacing:0.1em;padding:0 0 16px">
        <a href="{base}" style="color:{MUTED};text-decoration:none">gq.cueit.io</a>
        <span style="color:#C9C6BE">&nbsp;|&nbsp;</span>
        <a href="{base}/privacy" style="color:{MUTED};text-decoration:none">Privacy</a>
        <span style="color:#C9C6BE">&nbsp;|&nbsp;</span>
        <a href="{base}/terms" style="color:{MUTED};text-decoration:none">Terms</a>
      </td></tr>
      <tr><td style="text-align:center">
        <a href="{base}"><img src="{base}/cue-badge.png" alt="Cue" width="40" height="40"
             style="width:40px;height:40px;display:inline-block" /></a>
      </td></tr>
      <tr><td style="text-align:center;font-family:Helvetica,Arial,sans-serif;font-size:9.5px;
                     letter-spacing:0.22em;color:#A5A29A;padding:10px 0 0">
        PRODUCED ON CUE</td></tr>
    </table>

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
