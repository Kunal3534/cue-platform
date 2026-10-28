"""Google Drive helpers — Picker-chosen moodboards + Slides export.

Everything runs under the drive.file scope: the app can only touch files it
created or files the user explicitly picked in the Google Picker dialog.
"""
from __future__ import annotations

import json

import httpx

_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"

SLIDES_MIME = "application/vnd.google-apps.presentation"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


async def download_file(access_token: str, file_id: str, max_bytes: int) -> bytes | None:
    """Fetch a picked file's bytes; None on failure or if it's too large."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{_FILES_URL}/{file_id}",
            params={"alt": "media"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200 or len(resp.content) > max_bytes:
        return None
    return resp.content


async def set_link_viewable(access_token: str, file_id: str) -> bool:
    """'Anyone with the link can view' — so the moodboard embeds in briefs
    and keeps working on share links."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{_FILES_URL}/{file_id}/permissions",
            json={"role": "reader", "type": "anyone"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return resp.status_code in (200, 201)


async def upload_pptx_as_slides(access_token: str, name: str, pptx: bytes) -> str | None:
    """Upload a .pptx converted to native Google Slides; returns the
    presentation's view URL (None on failure)."""
    metadata = {"name": name, "mimeType": SLIDES_MIME}
    boundary = "cue-upload-boundary"
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\nContent-Type: {PPTX_MIME}\r\n\r\n"
    ).encode() + pptx + f"\r\n--{boundary}--".encode()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            _UPLOAD_URL,
            params={"uploadType": "multipart", "fields": "id,webViewLink"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
        )
    if resp.status_code not in (200, 201):
        return None
    data = resp.json()
    return data.get("webViewLink") or (
        f"https://docs.google.com/presentation/d/{data['id']}/edit" if data.get("id") else None
    )
