import enum
from datetime import UTC, datetime

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
    locations: str = Field(default="[]", sa_type=JSON)
    time_filter: str = "any"
    relevance: str = "recent"
    job_type: str | None = None
    experience: str | None = None
    on_site_or_remote: str | None = None
    industry: str = Field(default="[]", sa_type=JSON)
    base_salary: str | None = None
    job_function: str = Field(default="[]", sa_type=JSON)
    benefits: str = Field(default="[]", sa_type=JSON)
    commitments: str = Field(default="[]", sa_type=JSON)
    easy_apply: bool = False
    under_10_applicants: bool = False
    limit: int = 25
    days_back: int | None = None
    enabled: bool = True


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str = ""
