from datetime import UTC, datetime

from app.schemas import (
    JobRead,
    JobUpdate,
    ScrapeProgress,
    SearchQueryCreate,
    SearchQueryRead,
    SearchQueryUpdate,
    SettingUpdate,
)


class TestJobRead:
    def test_instantiation(self, db_session):
        from app.models import Job

        job = Job(
            linkedin_job_id="test_instantiation",
            title="Software Engineer",
            company="Test Corp",
            location="Remote",
            link="https://linkedin.com/jobs/view/123",
            apply_link="https://apply.test.com",
            description="We are looking for a software engineer.",
            date_posted="3 days ago",
            date_scraped=datetime.now(UTC),
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        data = JobRead.model_validate(job, from_attributes=True)
        assert data.id == job.id
        assert data.linkedin_job_id == job.linkedin_job_id
        assert data.title == job.title
        assert data.company == job.company
        assert data.location == job.location
        assert data.link == job.link
        assert data.apply_link == job.apply_link
        assert data.description == job.description
        assert data.date_posted == job.date_posted
        assert data.status == "new"
        assert data.fit_score is None
        assert data.notes == ""
        assert data.apply_link == "https://apply.test.com"

    def test_optional_fields_none(self, db_session):
        from app.models import Job

        job = Job(linkedin_job_id="minimal")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        data = JobRead.model_validate(job, from_attributes=True)
        assert data.fit_score is None
        assert data.fit_reason is None
        assert data.cv_change_recommended is None
        assert data.cv_change_reason is None
        assert data.matched_keywords is None
        assert data.tailored_cv_path is None
        assert data.tailored_cv_pdf_path is None
        assert data.cover_letter_path is None
        assert data.cover_letter_docx_path is None
        assert data.cover_letter_pdf_path is None
        assert data.applied_at is None
        assert data.apply_link is None
        assert data.date_posted is None


class TestJobUpdate:
    def test_all_fields_none(self):
        update = JobUpdate()
        assert update.status is None
        assert update.notes is None

    def test_partial_update(self):
        update = JobUpdate(status="applied")
        assert update.status == "applied"
        assert update.notes is None

    def test_exclude_unset(self):
        update = JobUpdate(notes="Updated notes")
        excluded = update.model_dump(exclude_unset=True)
        assert excluded == {"notes": "Updated notes"}

    def test_full_update(self):
        update = JobUpdate(status="interview", notes="Phone screen scheduled")
        assert update.status == "interview"
        assert update.notes == "Phone screen scheduled"


class TestSearchQueryCreate:
    def test_defaults(self):
        query = SearchQueryCreate()
        assert query.keywords == ""
        assert query.locations == []
        assert query.time_filter == "any"
        assert query.job_type is None
        assert query.experience is None
        assert query.on_site_or_remote is None
        assert query.limit == 25
        assert query.days_back is None
        assert query.enabled is True

    def test_custom_values(self):
        query = SearchQueryCreate(
            keywords="python developer",
            locations=["Remote", "Austin"],
            time_filter="month",
            job_type="contract",
            experience="entry",
            on_site_or_remote="hybrid",
            limit=10,
            days_back=14,
            enabled=False,
        )
        assert query.keywords == "python developer"
        assert query.locations == ["Remote", "Austin"]
        assert query.time_filter == "month"
        assert query.job_type == "contract"
        assert query.limit == 10
        assert query.days_back == 14
        assert query.enabled is False


class TestSearchQueryRead:
    def test_inherits_search_query_create(self):
        data = SearchQueryRead(
            id=1,
            keywords="engineer",
            locations=["Remote"],
            time_filter="any",
            limit=25,
            enabled=True,
        )
        assert data.id == 1
        assert data.keywords == "engineer"
        assert data.locations == ["Remote"]

    def test_with_all_fields(self):
        data = SearchQueryRead(
            id=42,
            keywords="data scientist",
            locations=["NYC", "SF"],
            time_filter="week",
            job_type="full-time",
            experience="senior",
            on_site_or_remote="remote",
            limit=50,
            days_back=7,
            enabled=False,
        )
        assert data.id == 42
        assert data.days_back == 7
        assert data.on_site_or_remote == "remote"


class TestSearchQueryUpdate:
    def test_all_fields_none(self):
        update = SearchQueryUpdate()
        assert update.keywords is None
        assert update.locations is None
        assert update.time_filter is None
        assert update.job_type is None
        assert update.experience is None
        assert update.on_site_or_remote is None
        assert update.limit is None
        assert update.days_back is None
        assert update.enabled is None

    def test_partial_update(self):
        update = SearchQueryUpdate(keywords="new keywords", limit=100)
        assert update.keywords == "new keywords"
        assert update.limit == 100
        assert update.locations is None
        assert update.time_filter is None

    def test_exclude_unset(self):
        update = SearchQueryUpdate(locations=["Remote"], enabled=False)
        excluded = update.model_dump(exclude_unset=True)
        assert excluded == {"locations": ["Remote"], "enabled": False}
        assert "keywords" not in excluded
        assert "limit" not in excluded


class TestSettingUpdate:
    def test_requires_value(self):
        update = SettingUpdate(value="new_value")
        assert update.value == "new_value"

    def test_serialization(self):
        update = SettingUpdate(value="prompt text here")
        dumped = update.model_dump()
        assert dumped == {"value": "prompt text here"}


class TestScrapeProgress:
    def test_defaults(self):
        progress = ScrapeProgress(running=False)
        assert progress.running is False
        assert progress.total == 0
        assert progress.current == 0
        assert progress.errors == 0
        assert progress.message == ""

    def test_custom_values(self):
        progress = ScrapeProgress(
            running=True,
            total=10,
            current=5,
            errors=1,
            message="Processing job 5 of 10",
        )
        assert progress.running is True
        assert progress.total == 10
        assert progress.current == 5
        assert progress.errors == 1
        assert progress.message == "Processing job 5 of 10"

    def test_partial_override(self):
        progress = ScrapeProgress(running=True, total=5)
        assert progress.running is True
        assert progress.total == 5
        assert progress.current == 0
        assert progress.errors == 0
        assert progress.message == ""
