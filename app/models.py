import enum
from datetime import UTC, datetime
from typing import Any

from sqlmodel import JSON, Field, SQLModel


class JobStatus(enum.StrEnum):
    new = "new"
    interested = "interested"
    applied = "applied"
    interview = "interview"
    rejected = "rejected"
    offer = "offer"
    accepted = "accepted"
    archived = "archived"
    ready = "ready"


class AutoPilotRun(SQLModel, table=True):
    __tablename__ = "autopilot_runs"

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"
    jobs_scraped: int = 0
    jobs_scored: int = 0
    jobs_tailored: int = 0
    jobs_cover_letter: int = 0
    errors: int = 0
    message: str = ""


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    linkedin_job_id: str = Field(unique=True, index=True, nullable=False)

    title: str = ""
    company: str = ""
    company_logo: str | None = None
    location: str = ""
    link: str = ""
    apply_link: str | None = None
    description: str = ""
    date_posted: str | None = None
    date_posted_dt: datetime | None = None
    date_scraped: datetime = Field(default_factory=lambda: datetime.now(UTC))

    viewed: bool = False
    status: JobStatus = Field(default=JobStatus.new)
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

    autopilot_processed_at: datetime | None = None
    applied_at: datetime | None = None
    notes: str = ""
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )


class SearchQuery(SQLModel, table=True):
    __tablename__ = "search_queries"

    id: int | None = Field(default=None, primary_key=True)
    keywords: str = ""
    locations: Any = Field(default="[]", sa_type=JSON)
    time_filter: str = "any"
    relevance: str = "recent"
    job_type: str | None = None
    experience: str | None = None
    on_site_or_remote: str | None = None
    industry: Any = Field(default="[]", sa_type=JSON)
    base_salary: str | None = None
    job_function: Any = Field(default="[]", sa_type=JSON)
    benefits: Any = Field(default="[]", sa_type=JSON)
    commitments: Any = Field(default="[]", sa_type=JSON)
    easy_apply: bool = False
    under_10_applicants: bool = False
    limit: int = 25
    days_back: int | None = None
    enabled: bool = True


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str = ""
