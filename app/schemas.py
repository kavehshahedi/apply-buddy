from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_ALLOWED_TIME_FILTERS = {"day", "week", "month", "any"}
_ALLOWED_RELEVANCE = {"recent", "relevant"}
_ALLOWED_JOB_TYPES = {"full_time", "part_time", "contract", "temporary", "internship", None}
_ALLOWED_EXPERIENCE = {
    "internship",
    "entry",
    "associate",
    "mid_senior",
    "director",
    "executive",
    None,
}
_ALLOWED_ON_SITE_REMOTE = {"on_site", "hybrid", "remote", None}


class JobRead(BaseModel):
    id: int = Field(ge=1)
    linkedin_job_id: str = Field(max_length=100)
    title: str = Field(max_length=500)
    company: str = Field(max_length=300)
    location: str = Field(max_length=300)
    link: str = Field(max_length=2000)
    apply_link: str | None = Field(default=None, max_length=2000)
    description: str = Field(max_length=50000)
    date_posted: str | None = Field(default=None, max_length=50)
    date_scraped: datetime
    status: str = Field(max_length=50)
    fit_score: int | None = Field(default=None, ge=0, le=100)
    fit_reason: str | None = Field(default=None, max_length=5000)
    cv_change_recommended: bool | None = None
    cv_change_reason: str | None = Field(default=None, max_length=5000)
    matched_keywords: str | None = Field(default=None, max_length=2000)
    tailored_cv_path: str | None = Field(default=None, max_length=500)
    tailored_cv_pdf_path: str | None = Field(default=None, max_length=500)
    cover_letter_path: str | None = Field(default=None, max_length=500)
    cover_letter_docx_path: str | None = Field(default=None, max_length=500)
    cover_letter_pdf_path: str | None = Field(default=None, max_length=500)
    applied_at: datetime | None = None
    notes: str = Field(default="", max_length=10000)
    updated_at: datetime


class JobUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=10000)


class SearchQueryCreate(BaseModel):
    keywords: str = Field(default="", max_length=200)
    locations: list[str] = Field(default_factory=list, max_length=50)
    time_filter: str = Field(default="any", max_length=20)
    relevance: str = Field(default="recent", max_length=20)
    job_type: str | None = Field(default=None, max_length=30)
    experience: str | None = Field(default=None, max_length=30)
    on_site_or_remote: str | None = Field(default=None, max_length=30)
    industry: list[str] = Field(default_factory=list, max_length=50)
    base_salary: str | None = Field(default=None, max_length=50)
    job_function: list[str] = Field(default_factory=list, max_length=50)
    benefits: list[str] = Field(default_factory=list, max_length=50)
    commitments: list[str] = Field(default_factory=list, max_length=50)
    easy_apply: bool = False
    under_10_applicants: bool = False
    limit: int = Field(default=25, ge=1, le=1000)
    days_back: int | None = Field(default=None, ge=1, le=365)
    enabled: bool = True

    @field_validator("time_filter")
    @classmethod
    def validate_time_filter(cls, v: str) -> str:
        if v not in _ALLOWED_TIME_FILTERS:
            raise ValueError(f"time_filter must be one of {_ALLOWED_TIME_FILTERS}")
        return v

    @field_validator("relevance")
    @classmethod
    def validate_relevance(cls, v: str) -> str:
        if v not in _ALLOWED_RELEVANCE:
            raise ValueError(f"relevance must be one of {_ALLOWED_RELEVANCE}")
        return v

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_JOB_TYPES:
            raise ValueError(f"job_type must be one of {_ALLOWED_JOB_TYPES}")
        return v

    @field_validator("experience")
    @classmethod
    def validate_experience(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_EXPERIENCE:
            raise ValueError(f"experience must be one of {_ALLOWED_EXPERIENCE}")
        return v

    @field_validator("on_site_or_remote")
    @classmethod
    def validate_on_site_or_remote(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_ON_SITE_REMOTE:
            raise ValueError(f"on_site_or_remote must be one of {_ALLOWED_ON_SITE_REMOTE}")
        return v


class SearchQueryRead(SearchQueryCreate):
    id: int


class SearchQueryUpdate(BaseModel):
    keywords: str | None = Field(default=None, max_length=200)
    locations: list[str] | None = Field(default=None, max_length=50)
    time_filter: str | None = Field(default=None, max_length=20)
    relevance: str | None = Field(default=None, max_length=20)
    job_type: str | None = Field(default=None, max_length=30)
    experience: str | None = Field(default=None, max_length=30)
    on_site_or_remote: str | None = Field(default=None, max_length=30)
    industry: list[str] | None = Field(default=None, max_length=50)
    base_salary: str | None = Field(default=None, max_length=50)
    job_function: list[str] | None = Field(default=None, max_length=50)
    benefits: list[str] | None = Field(default=None, max_length=50)
    commitments: list[str] | None = Field(default=None, max_length=50)
    easy_apply: bool | None = None
    under_10_applicants: bool | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)
    days_back: int | None = Field(default=None, ge=1, le=365)
    enabled: bool | None = None

    @field_validator("time_filter")
    @classmethod
    def validate_time_filter(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_TIME_FILTERS:
            raise ValueError(f"time_filter must be one of {_ALLOWED_TIME_FILTERS}")
        return v

    @field_validator("relevance")
    @classmethod
    def validate_relevance(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_RELEVANCE:
            raise ValueError(f"relevance must be one of {_ALLOWED_RELEVANCE}")
        return v

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_JOB_TYPES:
            raise ValueError(f"job_type must be one of {_ALLOWED_JOB_TYPES}")
        return v

    @field_validator("experience")
    @classmethod
    def validate_experience(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_EXPERIENCE:
            raise ValueError(f"experience must be one of {_ALLOWED_EXPERIENCE}")
        return v

    @field_validator("on_site_or_remote")
    @classmethod
    def validate_on_site_or_remote(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_ON_SITE_REMOTE:
            raise ValueError(f"on_site_or_remote must be one of {_ALLOWED_ON_SITE_REMOTE}")
        return v


class SettingUpdate(BaseModel):
    value: str = Field(max_length=50000)


class ScrapeProgress(BaseModel):
    running: bool
    total: int = Field(default=0, ge=0)
    current: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    message: str = ""


class InterviewSessionCreate(BaseModel):
    total_questions: int = Field(default=5, ge=1, le=30)


class InterviewAnswerSubmit(BaseModel):
    answer: str = Field(min_length=1, max_length=10000)
