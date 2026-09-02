from unittest.mock import MagicMock

import pytest

from app.models import InterviewSession, Job
from app.services.interview_prep import (
    DEFAULT_INTERVIEW_QUESTIONS_PROMPT,
    DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT,
    _llm_call_with_retry,
    _read_cv_text,
    _strip_tex_to_plain,
    generate_prep_pack,
    start_session,
    submit_answer,
)


def test_llm_call_with_retry_success(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"score": 85, "feedback": "Good"}'}}]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_call_with_retry(
        [{"role": "user", "content": "test"}], "test-model", max_retries=3
    )
    assert result == {"score": 85, "feedback": "Good"}


def test_llm_call_with_retry_strips_markdown_fences(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '```json\n{"score": 70, "feedback": "Okay"}\n```'}}]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_call_with_retry(
        [{"role": "user", "content": "test"}], "test-model", max_retries=3
    )
    assert result == {"score": 70, "feedback": "Okay"}


def test_llm_call_with_retry_retry_then_success(monkeypatch):
    call_count = [0]

    def mock_post(*args, **kwargs):
        call_count[0] += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        if call_count[0] < 3:
            mock_response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        else:
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"score": 90}'}}]
            }
        return mock_response

    monkeypatch.setattr("httpx.post", mock_post)
    result = _llm_call_with_retry(
        [{"role": "user", "content": "test"}], "test-model", max_retries=3
    )
    assert result == {"score": 90}
    assert call_count[0] == 3


def test_llm_call_with_retry_all_fail(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "not valid json"}}]}
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    with pytest.raises(RuntimeError, match="LLM response parsing failed after 3 attempts"):
        _llm_call_with_retry([{"role": "user", "content": "test"}], "test-model", max_retries=3)


def test_strip_tex_to_plain_basic():
    tex = r"\documentclass{article}\begin{document}Hello World\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "Hello World" in result


def test_strip_tex_to_plain_removes_commands():
    tex = r"\begin{document}\textbf{Bold} \textit{Italic}\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "Bold" in result
    assert "Italic" in result


def test_read_cv_text_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr("app.services.matcher.settings.cv_tex_path", "/nonexistent/path/cv.tex")
    result = _read_cv_text()
    assert result is None


def test_read_cv_text_with_file(monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.matcher.settings.cv_tex_path", str(cv_path))
    result = _read_cv_text()
    assert result is not None
    assert "Test CV" in result


def test_generate_prep_pack_no_job(db_session):
    state = {"running": True}
    generate_prep_pack(9999, state)
    assert state["message"] == "Job not found"
    assert state["running"] is False


def test_generate_prep_pack_success(db_session, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"questions": ["Q1", "Q2"], '
                        '"skills_gap": [{"skill": "Python", "required_level": "Advanced", '
                        '"candidate_level": "Intermediate", "gap_severity": "medium", '
                        '"recommendation": "Practice more"}]}'
                    )
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_prep",
        title="Software Engineer",
        company="Test Corp",
        description="Python developer role",
    )
    db_session.add(job)
    db_session.commit()

    state = {"running": True}
    generate_prep_pack(job.id, state)
    assert state["message"] == "Prep pack generated successfully"
    assert state["running"] is False

    session_obj = db_session.exec(
        __import__("sqlmodel").select(InterviewSession).where(InterviewSession.job_id == job.id)
    ).first()
    assert session_obj is not None
    assert "Q1" in session_obj.prep_questions
    assert "Python" in session_obj.prep_skills_gap


def test_generate_prep_pack_retry_then_success(db_session, monkeypatch):
    call_count = [0]

    def mock_post(*args, **kwargs):
        call_count[0] += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        if call_count[0] < 2:
            mock_response.json.return_value = {"choices": [{"message": {"content": "bad json"}}]}
        else:
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"questions": ["Q1"], "skills_gap": []}'}}]
            }
        return mock_response

    monkeypatch.setattr("httpx.post", mock_post)
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_prep_retry",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    state = {"running": True}
    generate_prep_pack(job.id, state)
    assert state["message"] == "Prep pack generated successfully"
    assert call_count[0] == 2


def test_generate_prep_pack_all_retries_fail(db_session, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "bad json"}}]}
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_prep_fail",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    state = {"running": True}
    generate_prep_pack(job.id, state)
    assert "Error" in state["message"]
    assert state["running"] is False


def test_start_session_no_prep_pack(db_session):
    job = Job(
        linkedin_job_id="test_no_prep",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    with pytest.raises(ValueError, match="No prep pack generated yet"):
        start_session(job.id, 5)


def test_start_session_success(db_session):
    job = Job(
        linkedin_job_id="test_start_session",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    prep = InterviewSession(
        job_id=job.id,
        prep_questions='["Q1", "Q2", "Q3", "Q4", "Q5"]',
        prep_skills_gap="[]",
    )
    db_session.add(prep)
    db_session.commit()

    session_obj = start_session(job.id, 3)
    assert session_obj.status == "in_progress"
    assert session_obj.total_questions == 3
    assert session_obj.current_question == 0
    questions = __import__("json").loads(session_obj.questions)
    assert questions == ["Q1", "Q2", "Q3"]


def test_start_session_clamps_to_available(db_session):
    job = Job(
        linkedin_job_id="test_clamp",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    prep = InterviewSession(
        job_id=job.id,
        prep_questions='["Q1", "Q2"]',
        prep_skills_gap="[]",
    )
    db_session.add(prep)
    db_session.commit()

    session_obj = start_session(job.id, 10)
    assert session_obj.total_questions == 2


def test_submit_answer_invalid_session(db_session):
    with pytest.raises(ValueError, match="Session not found"):
        submit_answer(9999, "test answer")


def test_submit_answer_success(db_session, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"score": 85, "feedback": "Good answer", '
                        '"model_answer": "A strong answer would...", '
                        '"key_strengths": ["Clear"], "areas_for_improvement": ["More detail"]}'
                    )
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_submit",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    session_obj = InterviewSession(
        job_id=job.id,
        status="in_progress",
        total_questions=2,
        current_question=0,
        questions='["Q1", "Q2"]',
        user_answers="[]",
        feedback="[]",
        prep_questions='["Q1", "Q2"]',
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    result = submit_answer(session_obj.id, "My answer")
    assert result["session_status"] == "in_progress"
    assert result["next_question"] == "Q2"
    assert result["feedback"]["score"] == 85
    assert result["feedback"]["feedback"] == "Good answer"


def test_submit_answer_last_question_completes_session(db_session, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"score": 90, "feedback": "Excellent", '
                        '"model_answer": "Perfect", '
                        '"key_strengths": ["Clear"], "areas_for_improvement": []}'
                    )
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_complete",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    session_obj = InterviewSession(
        job_id=job.id,
        status="in_progress",
        total_questions=1,
        current_question=0,
        questions='["Q1"]',
        user_answers="[]",
        feedback="[]",
        prep_questions='["Q1"]',
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    result = submit_answer(session_obj.id, "My answer")
    assert result["session_status"] == "completed"
    assert result["next_question"] is None

    db_session.refresh(session_obj)
    assert session_obj.status == "completed"
    assert session_obj.overall_summary != ""


def test_submit_answer_retry_then_success(db_session, monkeypatch):
    call_count = [0]

    def mock_post(*args, **kwargs):
        call_count[0] += 1
        mock_response = MagicMock()
        mock_response.status_code = 200
        if call_count[0] < 2:
            mock_response.json.return_value = {"choices": [{"message": {"content": "bad json"}}]}
        else:
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"score": 75, "feedback": "Good", '
                                '"model_answer": "Better", '
                                '"key_strengths": [], "areas_for_improvement": []}'
                            )
                        }
                    }
                ]
            }
        return mock_response

    monkeypatch.setattr("httpx.post", mock_post)
    monkeypatch.setattr(
        "app.services.interview_prep._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )

    job = Job(
        linkedin_job_id="test_submit_retry",
        title="Engineer",
        company="Co",
        description="Python role",
    )
    db_session.add(job)
    db_session.commit()

    session_obj = InterviewSession(
        job_id=job.id,
        status="in_progress",
        total_questions=1,
        current_question=0,
        questions='["Q1"]',
        user_answers="[]",
        feedback="[]",
        prep_questions='["Q1"]',
        prep_skills_gap="[]",
    )
    db_session.add(session_obj)
    db_session.commit()

    result = submit_answer(session_obj.id, "My answer")
    assert result["feedback"]["score"] == 75
    assert call_count[0] == 2


def test_default_prompts_contain_required_variables():
    assert "cv_plain" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT
    assert "job_title" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT
    assert "company" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT
    assert "description" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT
    assert "questions" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT
    assert "skills_gap" in DEFAULT_INTERVIEW_QUESTIONS_PROMPT

    assert "question" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "user_answer" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "job_title" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "company" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "description" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "cv_plain" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "score" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "feedback" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
    assert "model_answer" in DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT
