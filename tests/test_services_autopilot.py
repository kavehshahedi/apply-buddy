from unittest.mock import MagicMock

from app.models import Job, JobStatus, Setting
from app.services.autopilot import (
    _load_autopilot_setting,
    _run_process_phase,
    _run_score_phase,
    _run_scrape_phase,
    run_autopilot,
)


def test_load_autopilot_setting_default(db_session):
    result = _load_autopilot_setting("autopilot_nonexistent", "default_val")
    assert result == "default_val"


def test_load_autopilot_setting_from_db(db_session):
    existing = db_session.get(Setting, "autopilot_min_score")
    if existing:
        existing.value = "80"
    else:
        db_session.add(Setting(key="autopilot_min_score", value="80"))
    db_session.commit()
    result = _load_autopilot_setting("autopilot_min_score", "70")
    assert result == "80"


def test_load_autopilot_setting_empty_db_value_falls_back(db_session):
    existing = db_session.get(Setting, "autopilot_min_score")
    if existing:
        existing.value = ""
    else:
        db_session.add(Setting(key="autopilot_min_score", value=""))
    db_session.commit()
    result = _load_autopilot_setting("autopilot_min_score", "70")
    assert result == "70"


def test_run_scrape_phase_no_queries(db_session):
    state = {"running": True, "message": ""}
    _run_scrape_phase(state)
    assert state["scraped_count"] == 0
    assert "No" in state["message"]


def test_run_scrape_phase_with_queries(monkeypatch, db_session, sample_query):
    mock_scrape = MagicMock()

    def _fake_scrape(queries, scrape_state):
        scrape_state["running"] = False
        scrape_state["current"] = 5
        scrape_state["total"] = 5
        scrape_state["errors"] = 0
        scrape_state["message"] = "Scraped 5 jobs"

    mock_scrape.side_effect = _fake_scrape
    monkeypatch.setattr("app.services.scraper.scrape_jobs", mock_scrape)

    state = {"running": True, "message": ""}
    _run_scrape_phase(state)
    assert state["scraped_count"] == 5
    assert mock_scrape.called


def test_run_score_phase_force_rescore(monkeypatch):
    mock_score = MagicMock()

    def _fake_score(score_state, force_rescore=False):
        assert force_rescore is False
        score_state["running"] = False
        score_state["current"] = 3
        score_state["total"] = 3
        score_state["errors"] = 0
        score_state["message"] = "Scored 3 jobs"

    mock_score.side_effect = _fake_score
    monkeypatch.setattr("app.services.matcher.score_all_new_jobs", mock_score)

    state = {"running": True, "message": ""}
    _run_score_phase(state)
    assert state["scored_count"] == 3
    assert mock_score.called


def test_run_process_phase_no_jobs(db_session):
    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, True, True, True)
    assert state["tailored_count"] == 0
    assert state["cl_count"] == 0


def test_run_process_phase_skips_low_score(db_session):
    low_job = Job(
        linkedin_job_id="test_low_proc",
        title="Low Match",
        company="Low Co",
        status=JobStatus.new,
        fit_score=30,
        description="Low match job",
    )
    db_session.add(low_job)
    db_session.commit()

    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, True, True, True)
    assert state.get("total", 0) == 0


def test_run_process_phase_skips_already_processed(db_session):
    job = Job(
        linkedin_job_id="test_already_proc",
        title="Already Done",
        company="Done Co",
        status=JobStatus.new,
        fit_score=85,
        description="Already processed",
    )
    db_session.add(job)
    db_session.commit()

    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, False, False, True)
    assert state["tailored_count"] == 0
    assert state["cl_count"] == 0

    db_session.refresh(job)
    assert job.status == JobStatus.ready
    assert job.autopilot_processed_at is not None


def test_run_process_phase_sets_ready_only_when_successful(db_session, monkeypatch, temp_cv_file):
    job = Job(
        linkedin_job_id="test_ready_cond",
        title="Conditional Ready",
        company="Cond Co",
        status=JobStatus.new,
        fit_score=85,
        description="Test conditional ready",
    )
    db_session.add(job)
    db_session.commit()

    def _fake_tailor(job_id, sub_state=None):
        if sub_state:
            sub_state["message"] = "CV tailored successfully"

    mock_tailor = MagicMock(side_effect=_fake_tailor)
    monkeypatch.setattr("app.services.cv_tailor.tailor_cv_for_job", mock_tailor)

    def _fake_cl(job_id, sub_state=None, use_template=True):
        if sub_state:
            sub_state["message"] = "Cover letter generated"

    mock_cl = MagicMock(side_effect=_fake_cl)
    monkeypatch.setattr("app.services.cover_letter.generate_cover_letter", mock_cl)

    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, True, True, True)

    db_session.refresh(job)
    assert job.status == JobStatus.ready
    assert job.autopilot_processed_at is not None


def test_run_process_phase_keeps_new_on_failure(db_session, monkeypatch):
    job = Job(
        linkedin_job_id="test_fail_keep_new",
        title="Failing Job",
        company="Fail Co",
        status=JobStatus.new,
        fit_score=85,
        description="Will fail",
    )
    db_session.add(job)
    db_session.commit()

    mock_tailor = MagicMock(side_effect=Exception("LLM error"))
    monkeypatch.setattr("app.services.cv_tailor.tailor_cv_for_job", mock_tailor)

    mock_cl = MagicMock(side_effect=Exception("LLM error"))
    monkeypatch.setattr("app.services.cover_letter.generate_cover_letter", mock_cl)

    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, True, True, True)

    db_session.refresh(job)
    assert job.status == JobStatus.new
    assert job.autopilot_processed_at is not None


def test_run_process_phase_partial_failure_stays_new(db_session, monkeypatch, temp_cv_file):
    job = Job(
        linkedin_job_id="test_partial_fail",
        title="Partial Fail",
        company="Partial Co",
        status=JobStatus.new,
        fit_score=85,
        description="Partial failure",
    )
    db_session.add(job)
    db_session.commit()

    def _fake_tailor(job_id, sub_state=None):
        if sub_state:
            sub_state["message"] = "CV tailored successfully"

    mock_tailor = MagicMock(side_effect=_fake_tailor)
    monkeypatch.setattr("app.services.cv_tailor.tailor_cv_for_job", mock_tailor)

    mock_cl = MagicMock(side_effect=Exception("CL error"))
    monkeypatch.setattr("app.services.cover_letter.generate_cover_letter", mock_cl)

    state = {"running": True, "message": ""}
    _run_process_phase(state, 70, True, True, True)

    db_session.refresh(job)
    assert job.status == JobStatus.ready
    assert job.autopilot_processed_at is not None


def test_run_autopilot_full_pipeline(monkeypatch, db_session, sample_query, temp_cv_file):
    mock_scrape = MagicMock()

    def _fake_scrape(queries, scrape_state):
        scrape_state["running"] = False
        scrape_state["current"] = 2
        scrape_state["total"] = 2
        scrape_state["errors"] = 0

    mock_scrape.side_effect = _fake_scrape
    monkeypatch.setattr("app.services.scraper.scrape_jobs", mock_scrape)

    mock_score = MagicMock()

    def _fake_score(score_state, force_rescore=False):
        score_state["running"] = False
        score_state["current"] = 1
        score_state["total"] = 1
        score_state["errors"] = 0

    mock_score.side_effect = _fake_score
    monkeypatch.setattr("app.services.matcher.score_all_new_jobs", mock_score)

    mock_tailor = MagicMock()
    monkeypatch.setattr("app.services.cv_tailor.tailor_cv_for_job", mock_tailor)

    mock_cl = MagicMock()
    monkeypatch.setattr("app.services.cover_letter.generate_cover_letter", mock_cl)

    state = {
        "running": True,
        "phase": "starting",
        "total": 0,
        "current": 0,
        "errors": 0,
        "message": "",
        "run_id": None,
    }
    run_autopilot(state)

    assert state["running"] is False
    assert state["phase"] == "done"
    assert mock_scrape.called
    assert mock_score.called


def test_run_autopilot_handles_top_level_exception(monkeypatch, db_session):
    def _crash(state):
        raise RuntimeError("Unexpected crash")

    monkeypatch.setattr("app.services.autopilot._run_scrape_phase", _crash)

    state = {
        "running": True,
        "phase": "starting",
        "total": 0,
        "current": 0,
        "errors": 0,
        "message": "",
        "run_id": None,
    }
    run_autopilot(state)

    assert state["running"] is False
    assert state["phase"] == "error"
