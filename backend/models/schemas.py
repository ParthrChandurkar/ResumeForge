from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    resume_count: int
    has_cover_letter: bool
    setup_complete: bool


class TemplateOut(BaseModel):
    id: str
    name: str
    kind: Literal["resume", "cover_letter"]
    track: str
    filename: str
    content_type: str
    uploaded_at: datetime


class TailorRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=160)
    role_title: str = Field(min_length=1, max_length=200)
    job_description: str = Field(min_length=80, max_length=30000)
    template_id: str = Field(min_length=1, max_length=80)
    location: str | None = Field(default=None, max_length=160)
    job_id: str | None = Field(default=None, max_length=100)
    hiring_manager: str | None = Field(default=None, max_length=160)
    extra_instructions: str | None = Field(default=None, max_length=2000)


class TailorResult(BaseModel):
    id: str
    company_name: str
    role_title: str
    location: str | None
    job_id: str | None
    template_id: str
    template_name: str
    template_track: str
    job_description: str
    resume: dict
    cover_letter: dict
    match_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    tailoring_notes: list[str]
    created_at: datetime
    layout_profile: str = ""


class HistoryItem(BaseModel):
    id: str
    company_name: str
    role_title: str
    template_name: str
    template_track: str
    match_score: int
    created_at: datetime


class ContactDetails(BaseModel):
    name: str
    phone: str
    email: str
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class SkillGroup(BaseModel):
    label: str
    items: str


class ResumeEntry(BaseModel):
    title: str
    subtitle: str
    date: str
    location: str
    technologies: str
    bullets: list[str]
    url: str = ""


class Certification(BaseModel):
    name: str
    issuer: str = ""
    url: str = ""


class GeneratedResume(BaseModel):
    contact: ContactDetails
    headline: str
    profile_title: str
    profile: str
    skills_title: str
    skill_groups: list[SkillGroup]
    competency_bullets: list[str] = Field(default_factory=list)
    experience_title: str
    experiences: list[ResumeEntry]
    secondary_title: str
    secondary_entries: list[ResumeEntry]
    education_institution: str
    education_degree: str
    education_dates: str
    education_grade: str
    education_coursework: str
    certifications: list[Certification]


class EvidenceSection(BaseModel):
    heading: str
    body: str


class GeneratedCoverLetter(BaseModel):
    contact: ContactDetails
    recipient_team: str
    company: str
    location: str
    subject: str
    salutation: str
    opening: str
    evidence_sections: list[EvidenceSection]
    motivation: str
    closing: str


class GeminiTailoringOutput(BaseModel):
    resume: GeneratedResume
    cover_letter: GeneratedCoverLetter
    match_score: int = Field(ge=0, le=100)
    matched_keywords: list[str]
    missing_keywords: list[str]
    tailoring_notes: list[str]
