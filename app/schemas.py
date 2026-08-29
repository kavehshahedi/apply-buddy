from datetime import datetime

from pydantic import BaseModel


class JobRead(BaseModel):
    id: int
    linkedin_job_id: str
    title: str
    company: str
    location: str
    link: str
    apply_link: str | None = None
    description: str
    date_posted: str | None = None
    date_scraped: datetime
    status: str
    fit_score: int | None = None
    fit_reason: str | None = None
    cv_change_recommended: bool | None = None
    cv_change_reason: str | None = None
    matched_keywords: str | None = None
    tailored_cv_path: str | None = None
    tailored_cv_pdf_path: str | None = None
    cover_letter_path: str | None = None
    cover_letter_docx_path: str | None = None
    cover_letter_pdf_path: str | None = None
    applied_at: datetime | None = None
    notes: str
    updated_at: datetime


class JobUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class SearchQueryCreate(BaseModel):
    keywords: str = ""
    locations: list[str] = []
    time_filter: str = "any"
    relevance: str = "recent"
    job_type: str | None = None
    experience: str | None = None
    on_site_or_remote: str | None = None
    industry: list[str] = []
    base_salary: str | None = None
    job_function: list[str] = []
    benefits: list[str] = []
    commitments: list[str] = []
    easy_apply: bool = False
    under_10_applicants: bool = False
    limit: int = 25
    days_back: int | None = None
    enabled: bool = True


class SearchQueryRead(SearchQueryCreate):
    id: int


class SearchQueryUpdate(BaseModel):
    keywords: str | None = None
    locations: list[str] | None = None
    time_filter: str | None = None
    relevance: str | None = None
    job_type: str | None = None
    experience: str | None = None
    on_site_or_remote: str | None = None
    industry: list[str] | None = None
    base_salary: str | None = None
    job_function: list[str] | None = None
    benefits: list[str] | None = None
    commitments: list[str] | None = None
    easy_apply: bool | None = None
    under_10_applicants: bool | None = None
    limit: int | None = None
    days_back: int | None = None
    enabled: bool | None = None


class SettingUpdate(BaseModel):
    value: str


class ScrapeProgress(BaseModel):
    running: bool
    total: int = 0
    current: int = 0
    errors: int = 0
    message: str = ""
