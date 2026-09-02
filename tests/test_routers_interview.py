import json

import app.routers.interview as interview_router
from app.models import InterviewSession


def test_interview_page_returns_404(client, db_session):
    response = client.get("/interview/99999")
    assert response.status_code == 404


def test_interview_page_returns_200(client, sample_job):
    response = client.get(f"/interview/{sample_job.id}")
    assert response.status_code == 200
    assert "Interview Prep" in response.text
    assert "Generate Interview Prep Pack" in response.text
    assert sample_job.title in response.text


def test_interview_page_with_prep_pack(client, db_session, sample_job):
    prep = InterviewSession(
        job_id=sample_job.id,
        prep_questions=json.dumps(["Q1", "Q2"]),
        prep_skills_gap=json.dumps(
            [
                {
                    "skill": "Python",
                    "required_level": "Advanced",
                    "candidate_level": "Intermediate",
                    "gap_severity": "medium",
                    "recommendation": "Practice",
                }
            ]
        ),
    )
    db_session.add(prep)
    db_session.commit()

    response = client.get(f"/interview/{sample_job.id}")
    assert response.status_code == 200
    assert "Generate Interview Prep Pack" not in response.text
    assert "Likely Questions" in response.text
    assert "Skills Gap Analysis" in response.text
    assert "Mock Interview" in response.text
    assert "Q1" in response.text
    assert "Q2" in response.text
    assert "Python" in response.text


def test_interview_page_with_active_session(client, db_session, sample_job):
    session_obj = InterviewSession(
        job_id=sample_job.id,
        status="in_progress",
        questions=json.dumps(["Q1", "Q2"]),
        prep_questions=json.dumps(["Q1", "Q2"]),
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    response = client.get(f"/interview/{sample_job.id}")
    assert response.status_code == 200
    assert "Mock Interview" in response.text


def test_generate_prep_returns_404(client):
    response = client.post("/interview/99999/generate")
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_generate_prep_returns_200(client, sample_job):
    response = client.post(f"/interview/{sample_job.id}/generate")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_generate_prep_returns_409_when_running(client, sample_job):
    job_id = str(sample_job.id)
    interview_router._interview_generation_state[job_id] = {"running": True, "message": ""}
    try:
        response = client.post(f"/interview/{sample_job.id}/generate")
        assert response.status_code == 409
        assert response.json() == {"error": "Generation already running"}
    finally:
        interview_router._interview_generation_state.pop(job_id, None)


def test_interview_progress_returns_state(client, sample_job):
    job_id = str(sample_job.id)
    interview_router._interview_generation_state[job_id] = {"running": True, "message": "Working"}
    try:
        response = client.get(f"/interview/{sample_job.id}/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["message"] == "Working"
    finally:
        interview_router._interview_generation_state.pop(job_id, None)


def test_interview_progress_returns_default(client):
    response = client.get("/interview/99999/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["running"] is False
    assert data["message"] == ""


def test_start_session_returns_404(client):
    response = client.post(
        "/interview/99999/session",
        json={"total_questions": 5},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_start_session_returns_400_no_prep(client, sample_job):
    response = client.post(
        f"/interview/{sample_job.id}/session",
        json={"total_questions": 5},
    )
    assert response.status_code == 400
    assert "No prep pack generated yet" in response.json()["error"]


def test_start_session_returns_200(client, db_session, sample_job):
    prep = InterviewSession(
        job_id=sample_job.id,
        prep_questions=json.dumps(["Q1", "Q2", "Q3"]),
        prep_skills_gap="[]",
    )
    db_session.add(prep)
    db_session.commit()

    response = client.post(
        f"/interview/{sample_job.id}/session",
        json={"total_questions": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 2
    assert data["current_question"] == 0
    assert len(data["questions"]) == 2
    assert data["session_id"] is not None


def test_submit_answer_returns_404_no_session(client, sample_job):
    response = client.post(
        f"/interview/{sample_job.id}/session/99999/answer",
        json={"answer": "test"},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "Session not found"}


def test_submit_answer_returns_404_no_job(client):
    response = client.post(
        "/interview/99999/session/99999/answer",
        json={"answer": "test"},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_get_session_state_returns_200(client, db_session, sample_job):
    session_obj = InterviewSession(
        job_id=sample_job.id,
        status="in_progress",
        total_questions=2,
        current_question=0,
        questions=json.dumps(["Q1", "Q2"]),
        user_answers="[]",
        feedback="[]",
        prep_questions=json.dumps(["Q1", "Q2"]),
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    response = client.get(f"/interview/{sample_job.id}/session/{session_obj.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["total_questions"] == 2
    assert data["current_question"] == 0
    assert data["questions"] == ["Q1", "Q2"]


def test_get_session_state_returns_404_no_job(client):
    response = client.get("/interview/99999/session/99999")
    assert response.status_code == 404
    assert response.json() == {"error": "Job not found"}


def test_submit_answer_returns_500_on_llm_error(client, db_session, sample_job, monkeypatch):
    def mock_chat(*args, **kwargs):
        raise RuntimeError("LLM failed")

    monkeypatch.setattr("app.services.interview_prep.chat_completion", mock_chat)

    session_obj = InterviewSession(
        job_id=sample_job.id,
        status="in_progress",
        total_questions=1,
        current_question=0,
        questions=json.dumps(["Q1"]),
        user_answers="[]",
        feedback="[]",
        prep_questions=json.dumps(["Q1"]),
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    response = client.post(
        f"/interview/{sample_job.id}/session/{session_obj.id}/answer",
        json={"answer": "test"},
    )
    assert response.status_code == 500
    assert "error" in response.json()
