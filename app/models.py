import enum
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, JSON


class JobStatus(str, enum.Enum):
    new = "new"
    interested = "interested"
    applied = "applied"
    interview = "interview"
    rejected = "rejected"
    offer = "offer"
    accepted = "accepted"
    archived = "archived"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    linkedin_job_id: str = Field(unique=True, index=True, nullable=False)

    title: str = ""
    company: str = ""
    company_logo: Optional[str] = None
    location: str = ""
    link: str = ""
    apply_link: Optional[str] = None
    description: str = ""
    date_posted: Optional[str] = None
    date_posted_dt: Optional[datetime] = None
    date_scraped: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    viewed: bool = False
    status: JobStatus = Field(default=JobStatus.new)
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
    notes: str = ""
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
    )


class SearchQuery(SQLModel, table=True):
    __tablename__ = "search_queries"

    id: Optional[int] = Field(default=None, primary_key=True)
    keywords: str = ""
    locations: str = Field(default="[]", sa_type=JSON)
    time_filter: str = "any"
    job_type: Optional[str] = None
    experience: Optional[str] = None
    on_site_or_remote: Optional[str] = None
    limit: int = 25
    days_back: Optional[int] = None
    enabled: bool = True


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str = ""
