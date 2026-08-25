from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class JobRead(BaseModel):
    id: int
    linkedin_job_id: str
    title: str
    company: str
    location: str
    link: str
    apply_link: Optional[str] = None
    description: str
    date_posted: Optional[str] = None
    date_scraped: datetime
    status: str
    fit_score: Optional[int] = None
    fit_reason: Optional[str] = None
    cv_change_recommended: Optional[bool] = None
    cv_change_reason: Optional[str] = None
    matched_keywords: Optional[str] = None
    tailored_cv_path: Optional[str] = None
    tailored_cv_pdf_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    cover_letter_docx_path: Optional[str] = None
    cover_letter_pdf_path: Optional[str] = None
    applied_at: Optional[datetime] = None
    notes: str
    updated_at: datetime


class JobUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class SearchQueryCreate(BaseModel):
    keywords: str = ""
    locations: List[str] = []
    time_filter: str = "any"
    job_type: Optional[str] = None
    experience: Optional[str] = None
    on_site_or_remote: Optional[str] = None
    limit: int = 25
    days_back: Optional[int] = None
    enabled: bool = True


class SearchQueryRead(SearchQueryCreate):
    id: int


class SearchQueryUpdate(BaseModel):
    keywords: Optional[str] = None
    locations: Optional[List[str]] = None
    time_filter: Optional[str] = None
    job_type: Optional[str] = None
    experience: Optional[str] = None
    on_site_or_remote: Optional[str] = None
    limit: Optional[int] = None
    days_back: Optional[int] = None
    enabled: Optional[bool] = None


class SettingUpdate(BaseModel):
    value: str


class ScrapeProgress(BaseModel):
    running: bool
    total: int = 0
    current: int = 0
    errors: int = 0
    message: str = ""
