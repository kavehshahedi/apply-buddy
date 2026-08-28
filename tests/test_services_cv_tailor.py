from unittest.mock import MagicMock

from app.models import Job, Setting
from app.services.cv_tailor import (
    DEFAULT_TAILOR_CV_PROMPT,
    _llm_tailor_cv,
    _load_tailor_cv_model,
    _load_tailor_cv_prompt,
    tailor_cv_for_job,
)


def test_default_tailor_cv_prompt_constant():
    assert "title" in DEFAULT_TAILOR_CV_PROMPT
    assert "company" in DEFAULT_TAILOR_CV_PROMPT
    assert "description" in DEFAULT_TAILOR_CV_PROMPT
    assert "master_tex" in DEFAULT_TAILOR_CV_PROMPT
    assert "documentclass" in DEFAULT_TAILOR_CV_PROMPT


def test_load_tailor_cv_prompt_default():
    result = _load_tailor_cv_prompt()
    assert result == DEFAULT_TAILOR_CV_PROMPT


def test_load_tailor_cv_prompt_from_db(db_session):
    db_session.add(Setting(key="prompt_tailor_cv", value="Custom prompt {title} {company}"))
    db_session.commit()
    result = _load_tailor_cv_prompt()
    assert result == "Custom prompt {title} {company}"


def test_load_tailor_cv_model_default():
    result = _load_tailor_cv_model()
    assert result is None


def test_load_tailor_cv_model_from_db(db_session):
    db_session.add(Setting(key="prompt_tailor_cv_model", value="gpt-4o"))
    db_session.commit()
    result = _load_tailor_cv_model()
    assert result == "gpt-4o"


def test_llm_tailor_cv_strips_markdown_fences(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "```latex\n\\documentclass{article}\n\\begin{document}\nTailored Content\n\\end{document}\n```"
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_tailor_cv(
        "\\documentclass{article}\\begin{document}Original\\end{document}",
        "Engineer",
        "Co",
        "Description",
    )
    assert "\\documentclass" in result
    assert "\\end{document}" in result
    assert "Tailored Content" in result
    assert "```" not in result


def test_llm_tailor_cv_extracts_documentclass_to_end(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Here is the tailored CV:\n\n\\documentclass{article}\n\\begin{document}\nTailored\n\\end{document}\n\nLet me know if you need changes."
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_tailor_cv(
        "\\documentclass{article}\\begin{document}Original\\end{document}",
        "Engineer",
        "Co",
        "Description",
    )
    assert result.startswith("\\documentclass")
    assert result.endswith("\\end{document}")
    assert "Here is the tailored CV" not in result
    assert "Let me know" not in result


def test_llm_tailor_cv_returns_unchanged_when_no_documentclass(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Just some text without latex"}}]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_tailor_cv("raw tex", "Engineer", "Co", "Desc")
    assert result == "Just some text without latex"


def test_tailor_cv_for_job_not_found(db_session):
    state = {}
    tailor_cv_for_job(9999, state)
    assert "not found" in state["message"]


def test_tailor_cv_for_job_without_master_cv(db_session, monkeypatch):
    monkeypatch.setattr("app.services.cv_tailor.settings.cv_tex_path", "/nonexistent/path/cv.tex")
    job = Job(
        linkedin_job_id="test_cv_missing",
        title="Engineer",
        company="Co",
        description="Description",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    tailor_cv_for_job(job.id, state)
    assert "Master CV not found" in state["message"]


def test_tailor_cv_for_job_with_latex(
    mock_httpx_tex, db_session, mock_latex_available, monkeypatch, tmp_path
):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cv_tailor.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr("app.services.cv_tailor.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_tailor_latex",
        title="Software Engineer",
        company="Tech Corp",
        description="We need a Python developer.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    tailor_cv_for_job(job.id, state)
    db_session.refresh(job)
    assert job.tailored_cv_path is not None
    assert "cv.tex" in str(job.tailored_cv_path)
    assert "CV compiled" in state["message"] or "CV saved" in state["message"]


def test_tailor_cv_for_job_no_latex(
    mock_httpx_tex, db_session, mock_latex_unavailable, monkeypatch, tmp_path
):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cv_tailor.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr("app.services.cv_tailor.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_tailor_no_latex",
        title="Data Scientist",
        company="AI Co",
        description="ML experience required.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    tailor_cv_for_job(job.id, state)
    db_session.refresh(job)
    assert job.tailored_cv_path is not None
    assert (
        "LaTeX not available" in state["message"] or "PDF conversion disabled" in state["message"]
    )


def test_tailor_cv_for_job_convert_pdf_disabled(
    mock_httpx_tex, db_session, mock_latex_available, monkeypatch, tmp_path
):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cv_tailor.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr("app.services.cv_tailor.settings.output_dir", str(tmp_path))
    db_session.add(Setting(key="convert_cv_pdf", value="0"))
    db_session.commit()
    job = Job(
        linkedin_job_id="test_tailor_no_pdf",
        title="Backend Dev",
        company="Server Co",
        description="Backend experience.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    tailor_cv_for_job(job.id, state)
    db_session.refresh(job)
    assert job.tailored_cv_path is not None
    assert "PDF conversion disabled" in state["message"]
