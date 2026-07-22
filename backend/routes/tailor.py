import asyncio
import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from google import genai
from google.genai import types

from auth import User, require_user
from exact_templates import exact_source_path, render_cloud_resume, render_cover_letter
from latex import cover_letter_tex, resume_tex
from models.schemas import CompanyResearch, GeminiRevisionOutput, GeminiTailoringOutput, HistoryItem, RevisionRequest, ShortMessageOutput, TailorRequest, TailorResult
from storage import get_bytes, get_manifest, save_manifest

router = APIRouter(prefix="/tailor", tags=["Tailoring"])

SYSTEM_PROMPT = """You are an elite resume writer and career strategist. Tailor the authenticated user's selected resume to the supplied job description and write a matching cover letter using their uploaded cover-letter template.

NON-NEGOTIABLE RULES:
1. Preserve truth. Never invent employers, dates, qualifications, technologies, metrics, responsibilities, links, or achievements. Reframe and reorder only evidence present in the base resume.
2. Preserve the selected resume's section structure, contact details, and approximate content density so the result remains faithful to its original format.
3. Preserve the uploaded cover letter's tone, ordering, salutation style, evidence-heading style, closing, and approximate length.
4. Optimize naturally for ATS keywords from the job description without keyword stuffing.
5. Keep every bullet concise, impact-led, and evidence-based. Retain quantified outcomes where relevant.
6. Copy contact details, education, dates, grades, links, and certifications accurately from the base resume. The only experience/project hyperlink allowed is the IEEE publication link on the entry whose subtitle identifies the IEEE paper. Certificate URLs belong only in certification.url and must never be attached to an experience or project.
7. Return valid JSON only with exactly three evidence sections in the cover letter. The cover-letter subject must never begin with "Re:" because the renderer adds that prefix.
8. When the source resume has a separate bullet-based competency grid, preserve it in resume.competency_bullets instead of flattening it into skill groups.
9. The resume profile/summary is a professional evidence statement, never an application pitch. Never mention the target company, "seeking an opportunity", "excited to join", admiration, culture fit, or why the candidate wants the employer. Tailor capabilities and evidenced keywords only.
10. Keep the resume visually full without padding or invention. Preserve every original entry and bullet slot. For the cloud template, write a 55–75 word summary, exactly four skill groups, and evidence-rich bullets of roughly 25–40 words so the supplied one-page layout is used professionally.

Use the response schema exactly. The match score is a realistic 0–100 estimate after tailoring. Missing keywords must only describe genuine gaps that must not be fabricated."""

REVISION_PROMPT = """You revise an already-tailored resume and cover letter from one authenticated user's private workspace.

NON-NEGOTIABLE RULES:
1. Apply only the user's requested content change. Leave unrelated wording unchanged.
2. Never invent experience, employers, metrics, dates, technologies, qualifications, links, or achievements.
3. Preserve the exact document structure: section order and titles, entry order, entry count, bullet count, competency count, certification count, contact fields, and content density.
4. Never add, remove, edit, or move a URL. Return every URL in the same field and array position.
5. Preserve the selected resume template and cover-letter template. Do not suggest layout, font, spacing, color, or formatting changes.
6. The cover-letter subject must not begin with "Re:" because the renderer adds it.
7. Return both complete documents in the response schema, even when only one document changes.
8. Resume summary revisions must never mention the target company or contain job-seeking, enthusiasm, admiration, or employer-directed language.
9. If asked to fill the page or remove blank space, expand existing truthful evidence and ATS-relevant detail within the locked bullet slots; do not alter layout commands or invent facts.

Return valid structured output and a one-sentence change summary."""


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned an invalid document structure. Please regenerate.") from exc


def _clean_subject(value: object) -> str:
    """Store a subject without renderer-owned Re: prefixes."""
    return re.sub(r"^(?:\s*re\s*:\s*)+", "", str(value or ""), flags=re.IGNORECASE).strip()


def _clean_resume_profile(value: object, company_name: str) -> str:
    """Remove employer-directed language from a resume summary."""
    profile = " ".join(str(value or "").split())
    banned = (
        "seeking an opportunity", "seeking opportunity", "seeking to join", "eager to join",
        "excited to join", "excited to contribute", "looking to join", "looking for an opportunity",
        "aspiring to join", "drawn to", "thrilled to", "ideal fit", "culture fit",
    )
    company = company_name.strip().lower()
    sentences = re.split(r"(?<=[.!?])\s+", profile)
    kept = [sentence for sentence in sentences if not (company and company in sentence.lower()) and not any(phrase in sentence.lower() for phrase in banned)]
    cleaned = " ".join(kept).strip()
    if cleaned:
        return cleaned
    if company:
        profile = re.sub(re.escape(company_name), "", profile, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", profile).strip(" ,;.-")


def _precision_only(user: User, feature: str) -> None:
    if _layout_profile(user) != "precision":
        raise HTTPException(status_code=403, detail=f"{feature} is not enabled for this workspace yet")


async def _gemini_structured(api_key: str, prompt: str, schema: type, *, system: str = "", tools: list | None = None, tokens: int = 8000):
    """Generate schema-validated content with short retries for transient Gemini errors."""
    response = None
    for attempt in range(3):
        try:
            with genai.Client(api_key=api_key) as client:
                response = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system or None,
                        max_output_tokens=tokens,
                        response_mime_type="application/json",
                        response_schema=schema,
                        tools=tools,
                    ),
                )
            break
        except Exception as exc:
            message = str(exc).lower()
            transient = any(marker in message for marker in ("429", "503", "unavailable", "high demand", "rate limit"))
            if not transient or attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
    if response is None:
        raise RuntimeError("Gemini did not return a response")
    parsed = response.parsed
    if isinstance(parsed, schema):
        return parsed.model_dump(), response
    if isinstance(parsed, dict):
        return parsed, response
    return _parse_json(response.text or ""), response


def _find_run(manifest: dict, run_id: str) -> dict:
    run = next((item for item in manifest["runs"] if item["id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Tailoring session not found")
    return run


def _layout_profile(user: User) -> str:
    """Enable exact-template rendering only for privately configured user IDs."""
    configured = {item.strip() for item in os.getenv("PRECISION_LAYOUT_USER_IDS", "").split(",") if item.strip()}
    return "precision" if user.id in configured else ""


def _source_contact(text: str) -> dict:
    urls = re.findall(r"(?:https?://|mailto:|tel:)[^\s]+", text)
    return {
        "email": next((url.removeprefix("mailto:") for url in urls if url.startswith("mailto:")), ""),
        "github": next((url for url in urls if "github.com/" in url.lower()), ""),
        "linkedin": next((url for url in urls if "linkedin.com/" in url.lower()), ""),
        "portfolio": next((url for url in urls if url.startswith("http") and "vercel.app" in url.lower()), ""),
    }


def _restore_template_structure(run: dict, template: dict, user: User, cover_template: dict | None = None) -> dict:
    """Restore link targets and structural details that model output can omit."""
    letter = run.setdefault("cover_letter", {})
    letter["subject"] = _clean_subject(letter.get("subject", ""))
    profile = _layout_profile(user)
    if not profile:
        return run
    run["layout_profile"] = profile
    source = template.get("extracted_text", "")
    urls = re.findall(r"(?:https?://|mailto:|tel:)[^\s]+", source)
    resume = run.get("resume", {})
    resume["profile"] = _clean_resume_profile(resume.get("profile", ""), str(run.get("company_name", "")))
    contact = resume.setdefault("contact", {})
    contact_maps = _source_contact(source)
    for key, value in contact_maps.items():
        contact[key] = value
    letter_contact = letter.setdefault("contact", {})
    cover_contacts = _source_contact((cover_template or {}).get("extracted_text", ""))
    letter_contact["name"] = contact.get("name", letter_contact.get("name", ""))
    letter_contact["phone"] = contact.get("phone", letter_contact.get("phone", ""))
    for key in ("email", "github", "linkedin", "portfolio"):
        letter_contact[key] = cover_contacts.get(key, "")

    entries = [*resume.get("experiences", []), *resume.get("secondary_entries", [])]
    # Model output must never turn certificate URLs into blue experience/project subtitles.
    # Start from a clean slate and restore only the single source-backed IEEE paper link.
    for entry in entries:
        if isinstance(entry, dict):
            entry["url"] = ""
    publication_entry = next((entry for entry in entries if "ieee" in " ".join([
        str(entry.get("title", "")), str(entry.get("subtitle", "")), *map(str, entry.get("bullets", []))
    ]).lower()), None)
    publication_url = next((url for url in urls if "ieeexplore.ieee.org" in url.lower()), "")
    drive_urls = [url for url in urls if "drive.google.com" in url.lower()]
    certifications = resume.get("certifications", [])
    for item in certifications:
        if isinstance(item, dict):
            item["url"] = ""
    if publication_entry and not publication_url and len(drive_urls) > len([item for item in certifications if "progress" not in str(item).lower()]):
        publication_url = drive_urls.pop(0)
    if publication_entry and publication_url:
        publication_entry["url"] = publication_url
    elif publication_url and entries:
        entries[0]["url"] = publication_url

    for item in certifications:
        if not isinstance(item, dict) or "progress" in f"{item.get('name', '')} {item.get('issuer', '')}".lower():
            continue
        if drive_urls:
            item["url"] = drive_urls.pop(0)

    if template.get("track", "").lower() == "consulting" and not resume.get("competency_bullets"):
        match = re.search(r"Core Competencies\s*&\s*Tools\s*(.*?)(?:Cloud\s*&\s*Infrastructure\s*:)", source, re.IGNORECASE | re.DOTALL)
        if match:
            resume["competency_bullets"] = [part.strip() for part in match.group(1).split("•") if part.strip()]
    return run


def _lock_link_positions(previous: dict, revised: dict) -> None:
    """Prevent a revision from changing or moving any source-backed hyperlink."""
    for document_name in ("resume", "cover_letter"):
        old_contact = previous.get(document_name, {}).get("contact", {})
        new_contact = revised.get(document_name, {}).setdefault("contact", {})
        for key in ("phone", "email", "github", "linkedin", "portfolio"):
            new_contact[key] = old_contact.get(key, "")
    old_resume, new_resume = previous.get("resume", {}), revised.get("resume", {})
    for collection in ("experiences", "secondary_entries", "certifications"):
        old_items, new_items = old_resume.get(collection, []), new_resume.get(collection, [])
        if len(old_items) != len(new_items):
            raise HTTPException(status_code=502, detail="The revision attempted to change the locked template structure. Try a more specific text-only instruction.")
        for index, item in enumerate(new_items):
            if isinstance(item, dict) and isinstance(old_items[index], dict):
                item["url"] = old_items[index].get("url", "")
    for key in ("profile_title", "skills_title", "experience_title", "secondary_title"):
        new_resume[key] = old_resume.get(key, new_resume.get(key, ""))
    if len(old_resume.get("competency_bullets", [])) != len(new_resume.get("competency_bullets", [])):
        raise HTTPException(status_code=502, detail="The revision attempted to change the locked competency grid. Try a text-only instruction.")
    revised.setdefault("cover_letter", {})["subject"] = _clean_subject(revised.get("cover_letter", {}).get("subject", ""))


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

Tailor both documents while preserving truth, the resume structure, and the cover-letter template style.
The resume summary must use JD-relevant capabilities and keywords, but must not name the target company or say that the candidate is seeking, excited, eager, or applying to join it.
Use every existing resume entry and bullet slot. Keep bullets detailed enough to use the supplied one-page template fully, without adding any unsupported claim."""
    try:
        response = None
        for attempt in range(3):
            try:
                with genai.Client(api_key=api_key) as client:
                    response = client.models.generate_content(
                        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT, max_output_tokens=12000,
                            response_mime_type="application/json", response_schema=GeminiTailoringOutput,
                        ),
                    )
                break
            except Exception as exc:
                message = str(exc).lower()
                transient = any(marker in message for marker in ("429", "503", "unavailable", "high demand", "rate limit"))
                if not transient or attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        if response is None:
            raise RuntimeError("Gemini did not return a response")
        if isinstance(response.parsed, GeminiTailoringOutput):
            result = response.parsed.model_dump()
        elif isinstance(response.parsed, dict):
            result = response.parsed
        else:
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
        "revision_messages": [], "company_research": None, "short_message": "",
    }
    _restore_template_structure(run, template, user, cover)
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


@router.post("/{run_id}/revise", response_model=TailorResult)
async def revise_tailored_documents(run_id: str, payload: RevisionRequest, user: User = Depends(require_user)) -> dict:
    """Apply a text-only Gemini revision while locking the user's template and links."""
    _precision_only(user, "Revision chat")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured for this deployment")
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), None)
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), None)
    if not template:
        raise HTTPException(status_code=404, detail="The original resume template is no longer available")
    _restore_template_structure(run, template, user, cover_template)
    current_documents = {"resume": run["resume"], "cover_letter": run["cover_letter"]}
    user_prompt = f"""USER REVISION REQUEST:
{payload.instruction}

DOCUMENT TARGET: {payload.target}

TARGET ROLE: {run['role_title']}
TARGET COMPANY: {run['company_name']}

CURRENT TAILORED DOCUMENTS:
{json.dumps(current_documents, ensure_ascii=False)}

ORIGINAL RESUME EVIDENCE AND LINK SOURCE:
{template.get('extracted_text', '')[:30000]}

JOB DESCRIPTION:
{run.get('job_description', '')}

Apply only the requested text changes. Keep the full structure and every URL in its existing field and position."""
    if re.search(r"\b(fill|full|whole|blank|space|stretch|one[ -]?page)\b", payload.instruction, re.IGNORECASE):
        user_prompt += "\nThe user is asking for better page fill. Expand the existing summary and locked bullets with truthful JD-relevant detail from the source evidence; keep every count, link, and template field unchanged."
    try:
        response = None
        for attempt in range(3):
            try:
                with genai.Client(api_key=api_key) as client:
                    response = client.models.generate_content(
                        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=REVISION_PROMPT,
                            max_output_tokens=12000,
                            response_mime_type="application/json",
                            response_schema=GeminiRevisionOutput,
                        ),
                    )
                break
            except Exception as exc:
                message = str(exc).lower()
                transient = any(marker in message for marker in ("429", "503", "unavailable", "high demand", "rate limit"))
                if not transient or attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        if response is None:
            raise RuntimeError("Gemini did not return a response")
        if isinstance(response.parsed, GeminiRevisionOutput):
            revision = response.parsed.model_dump()
        elif isinstance(response.parsed, dict):
            revision = response.parsed
        else:
            revision = _parse_json(response.text or "")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini could not revise the documents: {exc}") from exc
    revised_documents = {"resume": revision["resume"], "cover_letter": revision["cover_letter"]}
    if payload.target == "resume":
        revised_documents["cover_letter"] = current_documents["cover_letter"]
    elif payload.target == "cover_letter":
        revised_documents["resume"] = current_documents["resume"]
    _lock_link_positions(current_documents, revised_documents)
    run["resume"] = revised_documents["resume"]
    run["cover_letter"] = revised_documents["cover_letter"]
    _restore_template_structure(run, template, user, cover_template)
    now = datetime.now(timezone.utc).isoformat()
    summary = str(revision.get("change_summary") or "Applied the requested text changes.").strip()
    run.setdefault("revision_messages", []).extend([
        {"role": "user", "content": payload.instruction.strip(), "created_at": now},
        {"role": "assistant", "content": summary, "created_at": now},
    ])
    run["revision_messages"] = run["revision_messages"][-20:]
    run["tailoring_notes"] = [*run.get("tailoring_notes", []), summary][-20:]
    await save_manifest(user.id, manifest)
    return run


@router.post("/{run_id}/company-research", response_model=TailorResult)
async def generate_company_research(run_id: str, user: User = Depends(require_user)) -> dict:
    """Build and save a current, Google-grounded company case study for Parth's workflow."""
    _precision_only(user, "Company History")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured for this deployment")
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), {})
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), {})
    _restore_template_structure(run, template, user, cover_template)
    prompt = f"""Research {run['company_name']} for a candidate applying to the {run['role_title']} role.
Use current, verifiable web information. Produce a concise but comprehensive company case study covering its origin, headquarters, current CEO/leadership, industry, activities, products/services, business model, relevant technology, ownership or publicly disclosed investors, major competitors, recent developments, culture/values, and useful application/interview angles.

JOB DESCRIPTION CONTEXT:
{run.get('job_description', '')[:12000]}

Rules:
- Do not guess. Clearly say "Not publicly disclosed" when ownership, investors, or technology cannot be verified.
- Keep each list focused and useful, not promotional.
- Include source page titles and direct HTTPS URLs used for the claims.
- Prefer the company's official pages, filings, reputable business publications, and investor sources."""
    try:
        research, response = await _gemini_structured(
            api_key, prompt, CompanyResearch,
            system="You are a rigorous company research analyst. Use Google Search, distinguish verified facts from unknowns, and never fabricate current information.",
            tools=[types.Tool(google_search=types.GoogleSearch())], tokens=10000,
        )
    except Exception as exc:
        if "429" in str(exc) or "resource_exhausted" in str(exc).lower():
            raise HTTPException(status_code=429, detail="Gemini's live company-research quota is temporarily exhausted. Wait a minute and press Research company again.") from exc
        raise HTTPException(status_code=502, detail=f"Gemini could not research the company: {exc}") from exc
    sources = research.get("sources", [])
    seen = {str(item.get("url", "")).rstrip("/") for item in sources if isinstance(item, dict)}
    try:
        metadata = response.candidates[0].grounding_metadata
        for chunk in metadata.grounding_chunks or []:
            web = getattr(chunk, "web", None)
            url = str(getattr(web, "uri", "") or "")
            if url.startswith("http") and url.rstrip("/") not in seen:
                sources.append({"title": str(getattr(web, "title", "Source") or "Source"), "url": url})
                seen.add(url.rstrip("/"))
    except (AttributeError, IndexError, TypeError):
        pass
    research["sources"] = [item for item in sources if isinstance(item, dict) and str(item.get("url", "")).startswith("http")][:12]
    run["company_research"] = research
    await save_manifest(user.id, manifest)
    return run


@router.post("/{run_id}/short-message", response_model=TailorResult)
async def generate_short_message(run_id: str, user: User = Depends(require_user)) -> dict:
    """Generate and save a concise application-form message from verified resume evidence."""
    _precision_only(user, "Short Message")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured for this deployment")
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), {})
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), {})
    _restore_template_structure(run, template, user, cover_template)
    prompt = f"""Write a professional application message for {run['role_title']} at {run['company_name']}.
Return exactly 5 short newline-separated lines, 60-100 words total. It will be pasted into a small application form, so do not add a subject, address, greeting, or signature. Connect the strongest truthful evidence in the tailored resume to the job description. Sound confident and specific, not flattering or desperate. Do not invent anything.

TAILORED RESUME:
{json.dumps(run.get('resume', {}), ensure_ascii=False)}

JOB DESCRIPTION:
{run.get('job_description', '')[:12000]}"""
    try:
        output, _ = await _gemini_structured(
            api_key, prompt, ShortMessageOutput,
            system="Write compact, evidence-based application messages. Follow the requested line count exactly.", tokens=1800,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini could not generate the short message: {exc}") from exc
    message = str(output.get("message", "")).strip()
    lines = [line.strip(" -\t") for line in message.splitlines() if line.strip()]
    if len(lines) not in (4, 5):
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(lines)) if part.strip()]
        if 4 <= len(sentences) <= 5:
            lines = sentences
    run["short_message"] = "\n".join(lines)
    await save_manifest(user.id, manifest)
    return run


@router.get("/{run_id}", response_model=TailorResult)
async def get_tailoring_run(run_id: str, user: User = Depends(require_user)) -> dict:
    """Return an authenticated user's complete previous tailoring session."""
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), {})
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), {})
    return _restore_template_structure(run, template, user, cover_template)


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
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), {})
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), {})
    _restore_template_structure(run, template, user, cover_template)
    tex = resume_tex(run)
    if run.get("layout_profile") == "precision" and template.get("track", "").lower() == "cloud":
        source = await get_bytes(exact_source_path(user.id, template["id"]))
        if source:
            tex = render_cloud_resume(source.decode("utf-8"), run["resume"])
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{user.name}-{run['company_name']}-Resume.tex")
    return Response(content=tex, media_type="application/x-tex", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{run_id}/cover-letter.tex")
async def download_cover_letter_tex(run_id: str, user: User = Depends(require_user)) -> Response:
    """Download an authenticated user's Overleaf-ready tailored cover-letter source."""
    manifest = await get_manifest(user.id)
    run = _find_run(manifest, run_id)
    template = next((item for item in manifest["templates"] if item["id"] == run.get("template_id")), {})
    cover_template = next((item for item in manifest["templates"] if item["kind"] == "cover_letter"), {})
    _restore_template_structure(run, template, user, cover_template)
    tex = cover_letter_tex(run)
    if run.get("layout_profile") == "precision" and cover_template:
        source = await get_bytes(exact_source_path(user.id, cover_template["id"]))
        if source:
            contact = run.get("cover_letter", {}).get("contact") or run.get("resume", {}).get("contact", {})
            tex = render_cover_letter(source.decode("utf-8"), run["cover_letter"], contact)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{user.name}-{run['company_name']}-Cover-Letter.tex")
    return Response(content=tex, media_type="application/x-tex", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
