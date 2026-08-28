from datetime import UTC, datetime, timedelta

from app.models import Job, JobStatus


def test_applied_board_returns_200(client, db_session):
    job_data = {
        "linkedin_job_id": "applied_1",
        "title": "Applied Engineer",
        "company": "Test Corp",
        "description": "A job",
        "date_posted_dt": datetime.now(UTC) - timedelta(days=1),
    }
    job = Job(**{**job_data, "status": JobStatus.applied})
    db_session.add(job)
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    assert "Applied Engineer" in response.text


def test_applied_board_includes_multiple_statuses(client, db_session):
    statuses = [
        JobStatus.applied,
        JobStatus.interview,
        JobStatus.rejected,
        JobStatus.offer,
        JobStatus.accepted,
    ]
    for i, status in enumerate(statuses):
        job = Job(
            linkedin_job_id=f"job_{i}",
            title=f"Job {status.value}",
            company="Test Corp",
            description="A job",
            status=status,
        )
        db_session.add(job)
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    for status in statuses:
        assert f"Job {status.value}" in response.text


def test_applied_board_excludes_new_and_interested(client, db_session):
    applied_job = Job(
        linkedin_job_id="applied_1",
        title="Applied Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.applied,
    )
    new_job = Job(
        linkedin_job_id="new_1",
        title="New Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.new,
    )
    interested_job = Job(
        linkedin_job_id="interested_1",
        title="Interested Job",
        company="Test Corp",
        description="A job",
        status=JobStatus.interested,
    )
    db_session.add_all([applied_job, new_job, interested_job])
    db_session.commit()

    response = client.get("/applied/")
    assert response.status_code == 200
    assert "Applied Job" in response.text
    assert "New Job" not in response.text
    assert "Interested Job" not in response.text
