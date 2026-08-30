from datetime import UTC

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Job, JobStatus, SearchQuery, Setting


class TestJobStatus:
    def test_enum_values(self):
        assert JobStatus.new.value == "new"
        assert JobStatus.interested.value == "interested"
        assert JobStatus.applied.value == "applied"
        assert JobStatus.interview.value == "interview"
        assert JobStatus.rejected.value == "rejected"
        assert JobStatus.offer.value == "offer"
        assert JobStatus.accepted.value == "accepted"
        assert JobStatus.archived.value == "archived"
        assert JobStatus.ready.value == "ready"

    def test_enum_order(self):
        values = [s.value for s in JobStatus]
        assert values == [
            "new",
            "interested",
            "applied",
            "interview",
            "rejected",
            "offer",
            "accepted",
            "archived",
            "ready",
        ]


class TestJobModel:
    def test_create_with_defaults(self, db_session):
        job = Job(linkedin_job_id="test_456")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.id is not None
        assert job.linkedin_job_id == "test_456"
        assert job.title == ""
        assert job.company == ""
        assert job.location == ""
        assert job.link == ""
        assert job.description == ""
        assert job.viewed is False
        assert job.status == JobStatus.new
        assert job.notes == ""
        assert job.fit_score is None
        assert job.fit_reason is None
        assert job.cv_change_recommended is None
        assert job.cv_change_reason is None
        assert job.matched_keywords is None
        assert job.apply_link is None
        assert job.company_logo is None
        assert job.date_posted is None
        assert job.date_posted_dt is None
        assert job.tailored_cv_path is None
        assert job.tailored_cv_pdf_path is None
        assert job.cover_letter_path is None
        assert job.cover_letter_docx_path is None
        assert job.cover_letter_pdf_path is None
        assert job.applied_at is None
        assert job.autopilot_processed_at is None
        assert job.date_scraped is not None
        assert job.updated_at is not None

    def test_create_with_custom_values(self, db_session):
        from datetime import datetime

        now = datetime.now(UTC)
        job = Job(
            linkedin_job_id="test_789",
            title="Senior Developer",
            company="Acme Inc",
            company_logo="https://logo.example.com/logo.png",
            location="San Francisco, CA",
            link="https://linkedin.com/jobs/view/789",
            apply_link="https://apply.acme.com",
            description="A senior role",
            date_posted="2 weeks ago",
            date_posted_dt=now,
            date_scraped=now,
            viewed=True,
            status=JobStatus.interested,
            fit_score=92,
            fit_reason="Excellent match",
            cv_change_recommended=True,
            cv_change_reason="Update skills section",
            matched_keywords="python, fastapi, sql",
            tailored_cv_path="/tmp/cv_789.tex",
            tailored_cv_pdf_path="/tmp/cv_789.pdf",
            cover_letter_path="/tmp/cl_789.md",
            cover_letter_docx_path="/tmp/cl_789.docx",
            cover_letter_pdf_path="/tmp/cl_789.pdf",
            applied_at=now,
            notes="Applied via company website",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.title == "Senior Developer"
        assert job.company == "Acme Inc"
        assert job.company_logo == "https://logo.example.com/logo.png"
        assert job.location == "San Francisco, CA"
        assert job.viewed is True
        assert job.status == JobStatus.interested
        assert job.fit_score == 92
        assert job.fit_reason == "Excellent match"
        assert job.cv_change_recommended is True
        assert job.cv_change_reason == "Update skills section"
        assert job.matched_keywords == "python, fastapi, sql"
        assert job.tailored_cv_path == "/tmp/cv_789.tex"
        assert job.notes == "Applied via company website"

    def test_linkedin_job_id_uniqueness(self, db_session, sample_job):
        duplicate = Job(linkedin_job_id=sample_job.linkedin_job_id)
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_default_status_is_new(self, db_session):
        job = Job(linkedin_job_id="test_status")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        assert job.status == JobStatus.new

    def test_status_update(self, db_session):
        job = Job(linkedin_job_id="test_status_update")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        job.status = JobStatus.applied
        db_session.commit()
        db_session.refresh(job)
        assert job.status == JobStatus.applied

    def test_viewed_default(self, db_session):
        job = Job(linkedin_job_id="test_viewed")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        assert job.viewed is False

    def test_notes_default(self, db_session):
        job = Job(linkedin_job_id="test_notes")
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        assert job.notes == ""


class TestSearchQueryModel:
    def test_create_with_defaults(self, db_session):
        query = SearchQuery()
        db_session.add(query)
        db_session.commit()
        db_session.refresh(query)

        assert query.id is not None
        assert query.keywords == ""
        assert query.locations == "[]"
        assert query.time_filter == "any"
        assert query.relevance == "recent"
        assert query.job_type is None
        assert query.experience is None
        assert query.on_site_or_remote is None
        assert query.industry == "[]"
        assert query.base_salary is None
        assert query.job_function == "[]"
        assert query.benefits == "[]"
        assert query.commitments == "[]"
        assert query.easy_apply is False
        assert query.under_10_applicants is False
        assert query.limit == 25
        assert query.days_back is None
        assert query.enabled is True

    def test_with_custom_values(self, db_session):
        query = SearchQuery(
            keywords="data scientist",
            locations='["New York", "Remote"]',
            time_filter="week",
            relevance="relevant",
            job_type="full-time",
            experience="mid-senior",
            on_site_or_remote="remote",
            industry='["software_development", "it_services"]',
            base_salary="100k",
            job_function='["engineering"]',
            benefits='["medical", "vision"]',
            commitments='["work_life_balance"]',
            easy_apply=True,
            under_10_applicants=True,
            limit=50,
            days_back=7,
            enabled=False,
        )
        db_session.add(query)
        db_session.commit()
        db_session.refresh(query)

        assert query.keywords == "data scientist"
        assert query.locations == '["New York", "Remote"]'
        assert query.time_filter == "week"
        assert query.relevance == "relevant"
        assert query.job_type == "full-time"
        assert query.experience == "mid-senior"
        assert query.on_site_or_remote == "remote"
        import json

        assert json.loads(query.industry) == ["software_development", "it_services"]
        assert query.base_salary == "100k"
        assert json.loads(query.job_function) == ["engineering"]
        assert json.loads(query.benefits) == ["medical", "vision"]
        assert json.loads(query.commitments) == ["work_life_balance"]
        assert query.easy_apply is True
        assert query.under_10_applicants is True
        assert query.limit == 50
        assert query.days_back == 7
        assert query.enabled is False

    def test_locations_json_storage(self, db_session):
        import json

        locations = ["Remote", "Austin, TX"]
        query = SearchQuery(keywords="engineer", locations=json.dumps(locations))
        db_session.add(query)
        db_session.commit()
        db_session.refresh(query)

        stored = json.loads(query.locations)
        assert stored == ["Remote", "Austin, TX"]

    def test_enabled_default(self, db_session):
        query = SearchQuery(keywords="test")
        db_session.add(query)
        db_session.commit()
        db_session.refresh(query)
        assert query.enabled is True


class TestSettingModel:
    def test_create(self, db_session):
        setting = Setting(key="prompt_score", value="Score this job")
        db_session.add(setting)
        db_session.commit()
        db_session.refresh(setting)

        assert setting.key == "prompt_score"
        assert setting.value == "Score this job"

    def test_default_value(self, db_session):
        setting = Setting(key="empty_setting")
        db_session.add(setting)
        db_session.commit()
        db_session.refresh(setting)
        assert setting.value == ""

    def test_primary_key_is_key(self):
        pk_columns = Setting.__table__.primary_key.columns.keys()
        assert "key" in pk_columns
        assert len(pk_columns) == 1


class TestAutoPilotRunModel:
    def test_create_with_defaults(self, db_session):
        from app.models import AutoPilotRun

        run = AutoPilotRun()
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        assert run.id is not None
        assert run.status == "running"
        assert run.started_at is not None
        assert run.completed_at is None
        assert run.jobs_scraped == 0
        assert run.jobs_scored == 0
        assert run.jobs_tailored == 0
        assert run.jobs_cover_letter == 0
        assert run.errors == 0
        assert run.message == ""

    def test_create_with_custom_values(self, db_session):
        from app.models import AutoPilotRun

        run = AutoPilotRun(
            status="completed",
            jobs_scraped=10,
            jobs_scored=8,
            jobs_tailored=5,
            jobs_cover_letter=3,
            errors=1,
            message="All done",
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        assert run.status == "completed"
        assert run.jobs_scraped == 10
        assert run.jobs_scored == 8
        assert run.jobs_tailored == 5
        assert run.jobs_cover_letter == 3
        assert run.errors == 1
        assert run.message == "All done"

    def test_status_transitions(self, db_session):
        from app.models import AutoPilotRun

        run = AutoPilotRun(status="running", message="Starting...")
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        assert run.status == "running"

        run.status = "completed"
        run.message = "Finished"
        db_session.commit()
        db_session.refresh(run)
        assert run.status == "completed"
        assert run.message == "Finished"
