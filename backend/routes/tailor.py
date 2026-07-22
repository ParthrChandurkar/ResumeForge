import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google import genai
from google.genai import types

from auth import User, require_user
from latex import cover_letter_tex, resume_tex
from models.schemas import GeminiTailoringOutput, HistoryItem, TailorRequest, TailorResult
from storage import get_manifest, save_manifest

router = APIRouter(prefix="/tailor", tags=["Tailoring"])

SYSTEM_PROMPT = """You are an elite resume writer and career strategist. Tailor the authenticated user's selected resume to the supplied job description and write a matching cover letter using their uploaded cover-letter template.

NON-NEGOTIABLE RULES:
1. Preserve truth. Never invent employers, dates, qualifications, technologies, metrics, responsibilities, links, or achievements. Reframe and reorder only evidence present in the base resume.
2. Preserve the selected resume's section structure, contact details, and approximate content density so the result remains faithful to its original format.
3. Preserve the uploaded cover letter's tone, ordering, salutation style, evidence-heading style, closing, and approximate length.
4. Optimize naturally for ATS keywords from the job description without keyword stuffing.
5. Keep every bullet concise, impact-led, and evidence-based. Retain quantified outcomes where relevant.
6. Copy contact details, education, dates, grades, links, and certifications accurately from the base resume. Retain every embedded URL in the matching contact field, experience.url, secondary_entries.url, or certification.url field.
7. Return valid JSON only with exactly three evidence sections in the cover letter.

Use the response schema exactly. The match score is a realistic 0–100 estimate after tailoring. Missing keywords must only describe genuine gaps that must not be fabricated."""


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned an invalid document structure. Please regenerate.") from exc


def _find_run(manifest: dict, run_id: str) -> dict:
    run = next((item for item in manifest["runs"] if item["id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Tailoring session not found")
    return run


@router.post("", response_model=TailorResult, status_code=status.HTTP_201_CREATED)
async def tailor_documents(payload: TailorRequest, user: User = Depends(require_user)) -> dict:
    """Tailor a user-owned resume and cover letter to a pasted job description."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured for this deployment")
    manifest = await get_manifest(user.id)
    template = next((item for item in manifest["templates"] if item["id"] == payload.template_id and item["kind"] == "resume"), None)
    cover = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), None)
    if not template:
        raise HTTPException(status_code=404, detail="Selected resume template not found")
    if not cover:
        raise HTTPException(status_code=409, detail="Upload a cover-letter template before tailoring")
    user_prompt = f"""USER: {user.name}
SELECTED RESUME TEMPLATE: {template['name']}
TEMPLATE TRACK: {template['track']}

--- BASE RESUME ---
{template['extracted_text'][:30000]}
--- END BASE RESUME ---

--- COVER LETTER TEMPLATE ---
{cover['extracted_text'][:20000]}
--- END COVER LETTER TEMPLATE ---

TARGET COMPANY: {payload.company_name}
TARGET ROLE: {payload.role_title}
LOCATION: {payload.location or 'Not provided'}
JOB ID: {payload.job_id or 'Not provided'}
HIRING MANAGER: {payload.hiring_manager or 'Recruiting Team'}
EXTRA INSTRUCTIONS: {payload.extra_instructions or 'None'}

--- JOB DESCRIPTION ---
{payload.job_description}
--- END JOB DESCRIPTION ---

Tailor both documents while preserving truth, the resume structure, and the cover-letter template style."""
    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT, temperature=0.2, max_output_tokens=7000,
                    response_mime_type="application/json", response_schema=GeminiTailoringOutput,
                ),
            )
        result = _parse_json(response.text or "")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini could not tailor the documents: {exc}") from exc
    required = {"resume", "cover_letter", "match_score", "matched_keywords", "missing_keywords", "tailoring_notes"}
    if not required.issubset(result):
        raise HTTPException(status_code=502, detail="Gemini returned an incomplete document set. Please regenerate.")
    run = {
        "id": uuid4().hex[:16], "company_name": payload.company_name, "role_title": payload.role_title,
        "location": payload.location, "job_id": payload.job_id, "template_id": template["id"],
        "template_name": template["name"], "template_track": template["track"],
        "job_description": payload.job_description, "resume": result["resume"], "cover_letter": result["cover_letter"],
        "match_score": max(0, min(100, int(result["match_score"]))),
        "matched_keywords": result["matched_keywords"], "missing_keywords": result["missing_keywords"],
        "tailoring_notes": result["tailoring_notes"], "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["runs"].insert(0, run)
    manifest["runs"] = manifest["runs"][:50]
    await save_manifest(user.id, manifest)
    return run


@router.get("/history", response_model=list[HistoryItem])
async def tailoring_history(user: User = Depends(require_user)) -> list[dict]:
    """Return only the authenticated user's recent tailoring sessions."""
    manifest = await get_manifest(user.id)
    keys = ("id", "company_name", "role_title", "template_name", "template_track", "match_score", "created_at")
    return [{key: run[key] for key in keys} for run in manifest["runs"]]


@router.get("/{run_id}", response_model=TailorResult)
async def get_tailoring_run(run_id: str, user: User = Depends(require_user)) -> dict:
    """Return an authenticated user's complete previous tailoring session."""
    return _find_run(await get_manifest(user.id), run_id)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tailoring_run(run_id: str, user: User = Depends(require_user)) -> Response:
    """Delete one authenticated user's saved tailoring session."""
    manifest = await get_manifest(user.id)
    _find_run(manifest, run_id)
    manifest["runs"] = [item for item in manifest["runs"] if item["id"] != run_id]
    await save_manifest(user.id, manifest)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{run_id}/resume.tex")
async def download_resume_tex(run_id: str, user: User = Depends(require_user)) -> Response:
    """Download an authenticated user's Overleaf-ready tailored resume source."""
    run = _find_run(await get_manifest(user.id), run_id)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{user.name}-{run['company_name']}-Resume.tex")
    return Response(content=resume_tex(run), media_type="application/x-tex", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{run_id}/cover-letter.tex")
async def download_cover_letter_tex(run_id: str, user: User = Depends(require_user)) -> Response:
    """Download an authenticated user's Overleaf-ready tailored cover-letter source."""
    run = _find_run(await get_manifest(user.id), run_id)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{user.name}-{run['company_name']}-Cover-Letter.tex")
    return Response(content=cover_letter_tex(run), media_type="application/x-tex", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
