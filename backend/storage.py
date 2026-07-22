import json
import os
from pathlib import Path
from typing import Any

from vercel.blob import AsyncBlobClient

LOCAL_ROOT = Path(__file__).resolve().parent / "user_data"
LOCAL_ROOT.mkdir(exist_ok=True)


def using_blob() -> bool:
    """Return whether durable Vercel Blob storage is configured."""
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


def _safe_local_path(path: str) -> Path:
    target = (LOCAL_ROOT / path).resolve()
    if LOCAL_ROOT.resolve() not in target.parents and target != LOCAL_ROOT.resolve():
        raise ValueError("Invalid storage path")
    return target


async def get_bytes(path: str) -> bytes | None:
    """Read private bytes from Vercel Blob or local development storage."""
    if using_blob():
        try:
            async with AsyncBlobClient() as client:
                result = await client.get(path, access="private", use_cache=False)
            return result.content if result.status_code == 200 else None
        except Exception:
            return None
    target = _safe_local_path(path)
    return target.read_bytes() if target.exists() else None


async def put_bytes(path: str, content: bytes, content_type: str) -> None:
    """Persist private bytes, overwriting the named user-owned object."""
    if using_blob():
        async with AsyncBlobClient() as client:
            await client.put(path, content, access="private", content_type=content_type, overwrite=True)
        return
    target = _safe_local_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


async def delete_object(path: str) -> None:
    """Delete a private stored object when it exists."""
    if using_blob():
        async with AsyncBlobClient() as client:
            await client.delete(path)
        return
    target = _safe_local_path(path)
    target.unlink(missing_ok=True)


async def get_json(path: str, default: Any) -> Any:
    """Read a JSON object from private storage with a safe default."""
    content = await get_bytes(path)
    if not content:
        return default
    try:
        return json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return default


async def put_json(path: str, value: Any) -> None:
    """Write a compact UTF-8 JSON object to private storage."""
    await put_bytes(path, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json")


def manifest_path(user_id: str) -> str:
    """Return the isolated manifest path for a user."""
    return f"users/{user_id}/manifest.json"


async def get_manifest(user_id: str) -> dict:
    """Read a user's isolated templates and generated-document history."""
    return await get_json(manifest_path(user_id), {"templates": [], "runs": []})


async def save_manifest(user_id: str, manifest: dict) -> None:
    """Persist a user's isolated templates and generated-document history."""
    await put_json(manifest_path(user_id), manifest)
