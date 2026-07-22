import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docx import Document
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pypdf import PdfReader

from auth import User, require_user
from models.schemas import TemplateOut
from storage import delete_object, get_bytes, get_manifest, put_bytes, save_manifest

router = APIRouter(prefix="/templates", tags=["Templates"])
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".tex"}


def extract_text(content: bytes, suffix: str) -> str:
    """Extract prompt-ready text from an uploaded resume or letter template."""
    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            chunks = []
            links = []
            for page in reader.pages:
                chunks.append(page.extract_text() or "")
                for reference in page.get("/Annots") or []:
                    annotation = reference.get_object()
                    action = annotation.get("/A")
                    uri = action.get("/URI") if action else None
                    if uri:
                        links.append(str(uri))
            if links:
                chunks.append("Embedded hyperlinks:\n" + "\n".join(dict.fromkeys(links)))
            return "\n".join(chunks)
        if suffix == ".docx":
            return "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
        return content.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The document could not be read. Try exporting it as PDF or UTF-8 .tex.") from exc


def public_template(item: dict) -> dict:
    """Remove private storage paths and extracted text from an API response."""
    return {key: item[key] for key in ("id", "name", "kind", "track", "filename", "content_type", "uploaded_at")}


@router.get("", response_model=list[TemplateOut])
async def list_templates(user: User = Depends(require_user)) -> list[dict]:
    """Return only the authenticated user's resume and cover-letter templates."""
    manifest = await get_manifest(user.id)
    return [public_template(item) for item in manifest["templates"]]


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    kind: str = Form(...),
    track: str = Form("custom"),
    user: User = Depends(require_user),
) -> dict:
    """Upload a user-owned resume or cover-letter template to private storage."""
    if kind not in {"resume", "cover_letter"}:
        raise HTTPException(status_code=400, detail="Template kind must be resume or cover_letter")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a PDF, DOCX, TXT, or Overleaf TEX file")
    content = await file.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Template files must be between 1 byte and 10 MB")
    extracted = extract_text(content, suffix)
    if len(extracted.strip()) < 40:
        raise HTTPException(status_code=400, detail="Not enough readable text was found in this file")
    template_id = uuid4().hex[:16]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file.filename or f"template{suffix}").strip("-")
    object_path = f"users/{user.id}/templates/{template_id}/{safe_name}"
    await put_bytes(object_path, content, file.content_type or "application/octet-stream")
    manifest = await get_manifest(user.id)
    if kind == "cover_letter":
        old_covers = [item for item in manifest["templates"] if item["kind"] == "cover_letter"]
        for old in old_covers:
            await delete_object(old["object_path"])
        manifest["templates"] = [item for item in manifest["templates"] if item["kind"] != "cover_letter"]
    item = {
        "id": template_id, "name": name.strip(), "kind": kind, "track": track.strip() or "custom",
        "filename": file.filename or safe_name, "content_type": file.content_type or "application/octet-stream",
        "object_path": object_path, "extracted_text": extracted,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["templates"].append(item)
    await save_manifest(user.id, manifest)
    return public_template(item)


@router.get("/{template_id}/original")
async def download_original_template(template_id: str, user: User = Depends(require_user)) -> Response:
    """Download an authenticated user's original private template file."""
    manifest = await get_manifest(user.id)
    item = next((entry for entry in manifest["templates"] if entry["id"] == template_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Template not found")
    content = await get_bytes(item["object_path"])
    if content is None:
        raise HTTPException(status_code=404, detail="Stored template file not found")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", item["filename"])
    return Response(content=content, media_type=item["content_type"], headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: str, user: User = Depends(require_user)) -> Response:
    """Delete one authenticated user's private template."""
    manifest = await get_manifest(user.id)
    item = next((entry for entry in manifest["templates"] if entry["id"] == template_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Template not found")
    await delete_object(item["object_path"])
    manifest["templates"] = [entry for entry in manifest["templates"] if entry["id"] != template_id]
    await save_manifest(user.id, manifest)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
