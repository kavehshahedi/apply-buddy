from unittest.mock import MagicMock

from app.models import Job, Setting
from app.services.matcher import (
    DEFAULT_SCORE_FIT_PROMPT,
    _keyword_score,
    _llm_score_job,
    _load_keywords,
    _load_min_keyword_score,
    _load_min_score,
    _read_cv_text,
    _read_cv_text_with_fallback,
    _strip_tex_to_plain,
    score_all_new_jobs,
    score_single_job,
)


def test_load_keywords_empty(db_session):
    result = _load_keywords()
    assert result == {}


def test_load_keywords_from_db(db_session):
    existing = db_session.get(Setting, "match_keywords")
    if existing:
        existing.value = '{"python": 2.0, "docker": 1.5}'
    else:
        db_session.add(Setting(key="match_keywords", value='{"python": 2.0, "docker": 1.5}'))
    db_session.commit()
    result = _load_keywords()
    assert result == {"python": 2.0, "docker": 1.5}


def test_load_keywords_from_db_invalid_json_falls_back(db_session):
    existing = db_session.get(Setting, "match_keywords")
    if existing:
        existing.value = "not json"
    else:
        db_session.add(Setting(key="match_keywords", value="not json"))
    db_session.commit()
    result = _load_keywords()
    assert result == {}


def test_load_min_score_default(db_session):
    result = _load_min_score()
    assert result == 30


def test_load_min_score_from_db(db_session):
    existing = db_session.get(Setting, "min_fit_score")
    if existing:
        existing.value = "50"
    else:
        db_session.add(Setting(key="min_fit_score", value="50"))
    db_session.commit()
    result = _load_min_score()
    assert result == 50


def test_load_min_score_invalid_value_falls_back(db_session):
    existing = db_session.get(Setting, "min_fit_score")
    if existing:
        existing.value = "abc"
    else:
        db_session.add(Setting(key="min_fit_score", value="abc"))
    db_session.commit()
    result = _load_min_score()
    assert result == 30


def test_load_min_keyword_score_default(db_session):
    result = _load_min_keyword_score()
    assert result == 0


def test_load_min_keyword_score_from_db(db_session):
    existing = db_session.get(Setting, "min_keyword_score")
    if existing:
        existing.value = "10"
    else:
        db_session.add(Setting(key="min_keyword_score", value="10"))
    db_session.commit()
    result = _load_min_keyword_score()
    assert result == 10


def test_load_min_keyword_score_invalid_value_falls_back(db_session):
    existing = db_session.get(Setting, "min_keyword_score")
    if existing:
        existing.value = "abc"
    else:
        db_session.add(Setting(key="min_keyword_score", value="abc"))
    db_session.commit()
    result = _load_min_keyword_score()
    assert result == 0


def test_keyword_score_matches():
    keywords = {"python": 2.0, "docker": 1.5, "kubernetes": 3.0}
    score, matched = _keyword_score(
        "Senior Python Developer", "Experience with Docker containers", keywords
    )
    assert score == 3.5
    assert "python" in matched
    assert "docker" in matched
    assert "kubernetes" not in matched


def test_keyword_score_no_match():
    keywords = {"golang": 2.0, "react": 1.0}
    score, matched = _keyword_score("Python Developer", "Experience with Django", keywords)
    assert score == 0.0
    assert matched == []


def test_keyword_score_empty_keywords():
    score, matched = _keyword_score("Python Developer", "Experience", {})
    assert score == 0.0
    assert matched == []


def test_keyword_score_case_insensitive():
    keywords = {"Python": 1.0, "DOCKER": 2.0}
    score, matched = _keyword_score("python developer", "experience with docker", keywords)
    assert score == 3.0
    assert "Python" in matched
    assert "DOCKER" in matched


def test_strip_tex_to_plain_basic():
    tex = r"\documentclass{article}\begin{document}Hello World\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "Hello World" in result


def test_strip_tex_to_plain_removes_comments():
    tex = r"\begin{document}Hello % this is a comment\nWorld\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "%" not in result


def test_strip_tex_to_plain_removes_commands():
    tex = r"\begin{document}\textbf{Bold} \textit{Italic}\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "Bold" in result
    assert "Italic" in result


def test_strip_tex_to_plain_handles_braces():
    tex = r"\begin{document}Hello {World}\end{document}"
    result = _strip_tex_to_plain(tex)
    assert "Hello" in result
    assert "World" in result


def test_strip_tex_to_plain_no_document_env():
    tex = r"Just plain text with \textbf{formatting}"
    result = _strip_tex_to_plain(tex)
    assert "plain text" in result


def test_read_cv_text_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr("app.services.matcher.settings.cv_tex_path", "/nonexistent/path/cv.tex")
    result = _read_cv_text()
    assert result is None


def test_read_cv_text_with_fallback_valid_path(monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.matcher._read_cv_text", lambda: None)
    result = _read_cv_text_with_fallback(str(cv_path))
    assert result is not None
    assert "Test CV" in result


def test_read_cv_text_with_fallback_invalid_path(monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text", lambda: cv_path.read_text(encoding="utf-8")
    )
    result = _read_cv_text_with_fallback("/nonexistent/path/cv.tex")
    assert result is not None
    assert "Test CV" in result


def test_read_cv_text_with_fallback_no_path(monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text", lambda: cv_path.read_text(encoding="utf-8")
    )
    result = _read_cv_text_with_fallback()
    assert result is not None
    assert "Test CV" in result


def test_llm_score_job_calls_chat_completion(mock_httpx, db_session):
    job = Job(
        linkedin_job_id="test_456",
        title="Data Scientist",
        company="AI Corp",
        description="Looking for a data scientist with ML experience.",
    )
    db_session.add(job)
    db_session.commit()
    cv_plain = "Experienced data scientist with ML background"
    result = _llm_score_job(job, cv_plain)
    assert result["fit_score"] == 85
    assert result["reason"] == "Great match"


def test_llm_score_job_strips_markdown_fences(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"fit_score": 70, "reason": "Good fit", "cv_change_recommended": true, "cv_change_reason": "Add ML projects"}\n```'
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    job = Job(
        linkedin_job_id="test_789",
        title="ML Engineer",
        company="ML Inc",
        description="ML engineering role",
    )
    cv_plain = "ML background"
    result = _llm_score_job(job, cv_plain)
    assert result["fit_score"] == 70
    assert result["cv_change_recommended"] is True


def test_score_all_new_jobs_no_jobs(monkeypatch, db_session):
    db_session.exec(__import__("sqlmodel").delete(Job))
    db_session.commit()
    monkeypatch.setattr("app.services.matcher._read_cv_text", lambda: None)
    state = {"errors": 0}
    score_all_new_jobs(state)
    assert state["message"] == "No new jobs to score"


def test_score_all_new_jobs_below_keyword_threshold(db_session, monkeypatch):
    db_session.exec(__import__("sqlmodel").delete(Job))
    db_session.commit()
    monkeypatch.setattr("app.services.matcher._load_min_keyword_score", lambda: 100)
    monkeypatch.setattr(
        "app.services.matcher._load_keywords",
        lambda: {"python": 10.0, "docker": 10.0},
    )
    monkeypatch.setattr("app.services.matcher._read_cv_text", lambda: None)
    job = Job(
        linkedin_job_id="test_kw",
        title="Junior Developer",
        company="Test Co",
        description="Entry level position",
    )
    db_session.add(job)
    db_session.commit()
    state = {"errors": 0}
    score_all_new_jobs(state)
    db_session.refresh(job)
    assert job.fit_score == 0
    assert job.fit_reason == "Below keyword threshold, skipped LLM scoring"


def test_score_all_new_jobs_full_llm_scoring(mock_httpx, db_session, monkeypatch):
    db_session.exec(__import__("sqlmodel").delete(Job))
    db_session.commit()
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )
    job = Job(
        linkedin_job_id="test_llm",
        title="Software Engineer",
        company="Test Corp",
        description="Python developer with experience",
    )
    db_session.add(job)
    db_session.commit()
    state = {"errors": 0}
    score_all_new_jobs(state)
    db_session.refresh(job)
    assert job.fit_score == 85
    assert job.fit_reason == "Great match"


def test_score_single_job_with_mock_httpx(mock_httpx, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text_with_fallback",
        lambda cv_path=None: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )
    job = Job(
        linkedin_job_id="test_single",
        title="Backend Engineer",
        company="Backend Co",
        description="Looking for a backend engineer with Python.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    score_single_job(job.id, state)
    db_session.refresh(job)
    assert job.fit_score == 85
    assert job.fit_reason == "Great match"


def test_score_single_job_not_found(db_session):
    state = {}
    score_single_job(9999, state)
    assert state["message"] == "Job not found"


def test_score_single_job_below_keyword_threshold(db_session, monkeypatch):
    monkeypatch.setattr("app.services.matcher._load_min_keyword_score", lambda: 100)
    monkeypatch.setattr(
        "app.services.matcher._load_keywords",
        lambda: {"python": 10.0},
    )
    job = Job(
        linkedin_job_id="test_single_kw",
        title="Junior Dev",
        company="Test",
        description="Entry level",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    score_single_job(job.id, state)
    db_session.refresh(job)
    assert job.fit_score == 0
    assert job.fit_reason == "Below keyword threshold, skipped LLM scoring"


def test_score_all_new_jobs_skips_scored_jobs(mock_httpx, db_session, monkeypatch):
    db_session.exec(__import__("sqlmodel").delete(Job))
    db_session.commit()
    monkeypatch.setattr("app.services.matcher._read_cv_text", lambda: None)
    job = Job(
        linkedin_job_id="test_already_scored",
        title="Engineer",
        company="Co",
        description="Python dev",
        fit_score=50,
        fit_reason="Already scored",
    )
    db_session.add(job)
    db_session.commit()
    state = {"errors": 0}
    score_all_new_jobs(state)
    assert state["message"] == "No new jobs to score"


def test_score_all_new_jobs_force_rescore(mock_httpx, db_session, monkeypatch):
    db_session.exec(__import__("sqlmodel").delete(Job))
    db_session.commit()
    monkeypatch.setattr(
        "app.services.matcher._read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )
    job = Job(
        linkedin_job_id="test_rescore",
        title="Engineer",
        company="Co",
        description="Python dev",
        fit_score=50,
        fit_reason="Already scored",
    )
    db_session.add(job)
    db_session.commit()
    state = {"errors": 0}
    score_all_new_jobs(state, force_rescore=True)
    db_session.refresh(job)
    assert job.fit_score == 85


def test_score_all_new_jobs_default_prompt_constant():
    assert "cv_plain" in DEFAULT_SCORE_FIT_PROMPT
    assert "job_title" in DEFAULT_SCORE_FIT_PROMPT
    assert "company" in DEFAULT_SCORE_FIT_PROMPT
    assert "description" in DEFAULT_SCORE_FIT_PROMPT
    assert "fit_score" in DEFAULT_SCORE_FIT_PROMPT
    assert "reason" in DEFAULT_SCORE_FIT_PROMPT
