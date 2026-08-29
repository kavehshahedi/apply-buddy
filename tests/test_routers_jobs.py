from sqlmodel import select

from app.models import Job, JobStatus


def test_job_list_returns_200(client, sample_job):
    response = client.get("/jobs/")
    assert response.status_code == 200
    assert "Software Engineer" in response.text


def test_job_list_filters_by_score(client, db_session, sample_job_data):
    job1 = Job(**{**sample_job_data, "linkedin_job_id": "test_1", "fit_score": 80})
    job2 = Job(**{**sample_job_data, "linkedin_job_id": "test_2", "fit_score": 30})
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/jobs/?sort=score&min_score=50")
    assert response.status_code == 200
    assert "test_1" in response.text or "Software Engineer" in response.text


def test_job_list_filters_by_source_linkedin(client, db_session, sample_job_data):
    job1 = Job(**{**sample_job_data, "linkedin_job_id": "test_1"})
    job2 = Job(**{**sample_job_data, "linkedin_job_id": "manual_abc123"})
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/jobs/?source=linkedin")
    assert response.status_code == 200


def test_job_list_filters_by_source_manual(client, db_session, sample_job_data):
    job1 = Job(**{**sample_job_data, "linkedin_job_id": "test_1"})
    job2 = Job(**{**sample_job_data, "linkedin_job_id": "manual_abc123"})
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/jobs/?source=manual")
    assert response.status_code == 200


def test_job_list_filters_by_viewed(client, db_session, sample_job_data):
    job1 = Job(**{**sample_job_data, "linkedin_job_id": "test_1", "viewed": True})
    job2 = Job(**{**sample_job_data, "linkedin_job_id": "test_2", "viewed": False})
    db_session.add_all([job1, job2])
    db_session.commit()

    response = client.get("/jobs/?viewed=viewed")
    assert response.status_code == 200

    response = client.get("/jobs/?viewed=unviewed")
    assert response.status_code == 200


def test_job_detail_returns_200(client, sample_job):
    response = client.get(f"/jobs/{sample_job.id}")
    assert response.status_code == 200
    assert "Software Engineer" in response.text


def test_job_detail_marks_as_viewed(client, db_session, sample_job):
    assert sample_job.viewed is False
    client.get(f"/jobs/{sample_job.id}")
    db_session.refresh(sample_job)
    assert sample_job.viewed is True


def test_job_detail_returns_404(client):
    response = client.get("/jobs/99999")
    assert response.status_code == 404


def test_create_manual_job(client, db_session):
    response = client.post(
        "/jobs/manual",
        data={
            "title": "New Job",
            "company": "New Corp",
            "description": "A new job description",
            "link": "https://example.com/job",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    jobs = db_session.exec(select(Job).where(Job.title == "New Job")).all()
    assert len(jobs) == 1


def test_create_manual_job_with_optional_fields(client, db_session):
    response = client.post(
        "/jobs/manual",
        data={
            "title": "Engineer",
            "company": "Tech Co",
            "description": "Engineering role",
            "location": "San Francisco",
            "link": "https://example.com/job2",
            "apply_link": "https://example.com/apply",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    jobs = db_session.exec(select(Job).where(Job.title == "Engineer")).all()
    assert len(jobs) == 1
    assert jobs[0].location == "San Francisco"
    assert jobs[0].link == "https://example.com/job2"
    assert jobs[0].apply_link == "https://example.com/apply"


def test_create_manual_job_duplicate_link(client, db_session, sample_job):
    response = client.post(
        "/jobs/manual",
        data={
            "title": "Dup Job",
            "company": "Dup Corp",
            "description": "Another description",
            "link": sample_job.link,
        },
        follow_redirects=False,
    )
    assert response.status_code == 409
    jobs = db_session.exec(select(Job).where(Job.title == "Dup Job")).all()
    assert len(jobs) == 0


def test_update_job_status(client, db_session, sample_job):
    response = client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "interested"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(sample_job)
    assert sample_job.status == JobStatus.interested


def test_update_job_status_sets_applied_at(client, db_session, sample_job):
    response = client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "applied"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(sample_job)
    assert sample_job.status == JobStatus.applied
    assert sample_job.applied_at is not None


def test_update_job_status_updates_notes(client, db_session, sample_job):
    response = client.post(
        f"/jobs/{sample_job.id}/status",
        data={"status": "interested", "notes": "Follow up next week"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(sample_job)
    assert sample_job.notes == "Follow up next week"


def test_update_job_status_returns_404(client, db_session):
    response = client.post(
        "/jobs/99999/status",
        data={"status": "interested"},
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_delete_job(client, db_session, sample_job):
    response = client.post(
        f"/jobs/{sample_job.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db_session.exec(select(Job.id).where(Job.id == sample_job.id)).first() is None


def test_delete_job_returns_404(client):
    response = client.post(
        "/jobs/99999/delete",
        follow_redirects=False,
    )
    assert response.status_code == 404
