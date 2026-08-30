from unittest.mock import MagicMock

import app.routers.autopilot as autopilot_router
from app.models import Job, JobStatus


def test_autopilot_run_returns_200(client, sample_query, monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("app.services.autopilot.run_autopilot", mock_run)

    response = client.post("/autopilot/run")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_autopilot_run_returns_409_when_already_running(client, sample_query, monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("app.services.autopilot.run_autopilot", mock_run)

    autopilot_router._autopilot_state["running"] = True
    try:
        response = client.post("/autopilot/run")
        assert response.status_code == 409
        assert response.json() == {"error": "Auto-Pilot already running"}
    finally:
        autopilot_router._autopilot_state["running"] = False


def test_autopilot_progress_returns_state(client, sample_query, monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("app.services.autopilot.run_autopilot", mock_run)

    response = client.get("/autopilot/progress")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "phase" in data
    assert "total" in data
    assert "current" in data
    assert "errors" in data
    assert "message" in data


def test_autopilot_queue_returns_html(client, db_session):
    job = Job(
        linkedin_job_id="test_ready_1",
        title="Ready Engineer",
        company="Ready Corp",
        status=JobStatus.ready,
        fit_score=85,
        description="A great job",
    )
    db_session.add(job)
    db_session.commit()

    response = client.get("/autopilot/queue")
    assert response.status_code == 200
    assert "Ready Engineer" in response.text


def test_autopilot_queue_omits_non_ready(client, db_session):
    new_job = Job(
        linkedin_job_id="test_new_1",
        title="New Engineer",
        company="New Corp",
        status=JobStatus.new,
        fit_score=85,
        description="A new job",
    )
    db_session.add(new_job)
    db_session.commit()

    response = client.get("/autopilot/queue")
    assert response.status_code == 200
    assert "New Engineer" not in response.text


def test_autopilot_queue_filters_by_min_score(client, db_session):
    low = Job(
        linkedin_job_id="test_low_1",
        title="Low Score",
        company="Low Corp",
        status=JobStatus.ready,
        fit_score=30,
        description="Low match",
    )
    db_session.add(low)
    db_session.commit()

    response = client.get("/autopilot/queue")
    assert response.status_code == 200
    assert "Low Score" not in response.text


def test_autopilot_queue_shows_empty_state(client):
    response = client.get("/autopilot/queue")
    assert response.status_code == 200
    assert "No jobs ready yet" in response.text


def test_autopilot_reset_returns_200(client, db_session):
    job = Job(
        linkedin_job_id="test_reset_1",
        title="Reset Me",
        company="Reset Corp",
        status=JobStatus.ready,
        fit_score=85,
        description="To be reset",
    )
    db_session.add(job)
    db_session.commit()

    response = client.post("/autopilot/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["reset_count"] == 1

    db_session.refresh(job)
    assert job.status == JobStatus.new
    assert job.autopilot_processed_at is None


def test_autopilot_reset_no_ready_jobs(client):
    response = client.post("/autopilot/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["reset_count"] == 0


def test_autopilot_reset_only_ready_jobs(client, db_session):
    new_job = Job(
        linkedin_job_id="test_new_reset",
        title="New Not Reset",
        company="New Corp",
        status=JobStatus.new,
        fit_score=50,
        description="Should stay new",
    )
    db_session.add(new_job)
    db_session.commit()

    response = client.post("/autopilot/reset")
    assert response.status_code == 200
    assert response.json()["reset_count"] == 0

    db_session.refresh(new_job)
    assert new_job.status == JobStatus.new
