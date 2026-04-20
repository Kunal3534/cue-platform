"""StorageService — thin boto3 wrapper for S3 / MinIO.

Key scheme (spec §10):
  call_sheets/{project_id}/{day_id}/v{version}.pdf
  exports/{project_id}/{job_id}.zip
  exports/{project_id}/{view}-{ts}.xlsx
  uploads/{project_id}/master_{ts}.xlsx
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import boto3
from botocore.client import Config

from ..config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    return settings.s3_bucket


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def key_callsheet(project_id: str, day_id: str, version: int) -> str:
    return f"call_sheets/{project_id}/{day_id}/v{version}.pdf"


def key_export_zip(project_id: str, job_id: str) -> str:
    return f"exports/{project_id}/{job_id}.zip"


def key_export_xlsx(project_id: str, view: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"exports/{project_id}/{view}-{ts}.xlsx"


def key_upload(project_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"uploads/{project_id}/master_{ts}.xlsx"


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def ensure_bucket() -> None:
    client = _client()
    bucket = _bucket()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes; returns the S3 key."""
    _client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def put_file(key: str, path: str, content_type: str = "application/octet-stream") -> str:
    """Upload a local file by path; returns the S3 key."""
    with open(path, "rb") as f:
        return put_bytes(key, f.read(), content_type)


def get_bytes(key: str) -> bytes:
    resp = _client().get_object(Bucket=_bucket(), Key=key)
    return resp["Body"].read()


def presigned_url(key: str, expires_seconds: int = 3600) -> str:
    """Return a pre-signed GET URL valid for `expires_seconds`."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_seconds,
    )


def delete(key: str) -> None:
    _client().delete_object(Bucket=_bucket(), Key=key)
