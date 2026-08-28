import app.routers.actions as actions_router


def test_score_fit_returns_200(client, mock_matcher_batch):
    response = client.post("/actions/score-fit")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_score_fit_returns_409_when_already_running(client, mock_matcher_batch):
    actions_router._score_state["running"] = True
    try:
        response = client.post("/actions/score-fit")
        assert response.status_code == 409
        assert response.json() == {"error": "Scoring already running"}
    finally:
        actions_router._score_state["running"] = False


def test_score_progress_returns_state(client):
    response = client.get("/actions/score-progress")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert "total" in data
    assert "current" in data
    assert "errors" in data
    assert "message" in data


def test_score_fit_single_returns_200(client, sample_job, mock_matcher_single):
    response = client.post(f"/actions/score-fit/{sample_job.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_score_fit_single_returns_404(client, mock_matcher_single):
    response = client.post("/actions/score-fit/99999")
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_score_fit_single_returns_409_when_already_running(client, sample_job, mock_matcher_single):
    job_id = str(sample_job.id)
    actions_router._action_state[job_id] = {"running": True, "message": "", "action": "score-fit"}
    try:
        response = client.post(f"/actions/score-fit/{sample_job.id}")
        assert response.status_code == 409
        assert response.json() == {"error": "Scoring already running for this job"}
    finally:
        actions_router._action_state.pop(job_id, None)


def test_tailor_cv_returns_200(client, sample_job, mock_cv_tailor):
    response = client.post(f"/actions/tailor-cv/{sample_job.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_tailor_cv_returns_404(client, mock_cv_tailor):
    response = client.post("/actions/tailor-cv/99999")
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_cover_letter_returns_200(client, sample_job, mock_cover_letter):
    response = client.post(f"/actions/cover-letter/{sample_job.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_cover_letter_returns_404(client, mock_cover_letter):
    response = client.post("/actions/cover-letter/99999")
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_action_progress_returns_state_for_existing_job(client, sample_job):
    job_id = str(sample_job.id)
    actions_router._action_state[job_id] = {
        "running": True,
        "message": "Working",
        "action": "score-fit",
    }
    try:
        response = client.get(f"/actions/action-progress/{sample_job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["message"] == "Working"
        assert data["action"] == "score-fit"
    finally:
        actions_router._action_state.pop(job_id, None)


def test_action_progress_returns_default_for_missing_job(client):
    response = client.get("/actions/action-progress/99999")
    assert response.status_code == 200
    data = response.json()
    assert data["running"] is False
    assert data["message"] == ""


def test_download_file_returns_404_when_not_found(client, sample_job):
    response = client.get(f"/actions/download/{sample_job.id}/nonexistent.pdf")
    assert response.status_code == 404
    assert response.json() == {"error": "File not found"}
