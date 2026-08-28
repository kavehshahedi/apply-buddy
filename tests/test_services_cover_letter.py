from unittest.mock import MagicMock

from app.models import Job, Setting
from app.services.cover_letter import (
    DEFAULT_COVER_LETTER_PROMPT,
    DEFAULT_COVER_LETTER_TEMPLATE_PROMPT,
    _llm_cover_letter,
    _load_cover_letter_model,
    _load_cover_letter_prompt,
    _load_cover_letter_template_model,
    _load_cover_letter_template_prompt,
    generate_cover_letter,
)


def test_default_cover_letter_prompt_constant():
    assert "title" in DEFAULT_COVER_LETTER_PROMPT
    assert "company" in DEFAULT_COVER_LETTER_PROMPT
    assert "description" in DEFAULT_COVER_LETTER_PROMPT
    assert "cv_text" in DEFAULT_COVER_LETTER_PROMPT
    assert "Markdown" in DEFAULT_COVER_LETTER_PROMPT


def test_default_cover_letter_template_prompt_constant():
    assert "title" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT
    assert "company" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT
    assert "description" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT
    assert "cv_text" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT
    assert "template" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT
    assert "Markdown" in DEFAULT_COVER_LETTER_TEMPLATE_PROMPT


def test_load_cover_letter_prompt_default():
    result = _load_cover_letter_prompt()
    assert result == DEFAULT_COVER_LETTER_PROMPT


def test_load_cover_letter_prompt_from_db(db_session):
    db_session.add(Setting(key="prompt_cover_letter", value="Custom prompt {title}"))
    db_session.commit()
    result = _load_cover_letter_prompt()
    assert result == "Custom prompt {title}"


def test_load_cover_letter_template_prompt_default():
    result = _load_cover_letter_template_prompt()
    assert result == DEFAULT_COVER_LETTER_TEMPLATE_PROMPT


def test_load_cover_letter_template_prompt_from_db(db_session):
    db_session.add(Setting(key="prompt_cover_letter_template", value="Template prompt {template}"))
    db_session.commit()
    result = _load_cover_letter_template_prompt()
    assert result == "Template prompt {template}"


def test_load_cover_letter_model_default():
    assert _load_cover_letter_model() is None


def test_load_cover_letter_model_from_db(db_session):
    db_session.add(Setting(key="prompt_cover_letter_model", value="gpt-4o"))
    db_session.commit()
    result = _load_cover_letter_model()
    assert result == "gpt-4o"


def test_load_cover_letter_template_model_default():
    assert _load_cover_letter_template_model() is None


def test_load_cover_letter_template_model_from_db(db_session):
    db_session.add(Setting(key="prompt_cover_letter_template_model", value="gpt-4o-mini"))
    db_session.commit()
    result = _load_cover_letter_template_model()
    assert result == "gpt-4o-mini"


def test_llm_cover_letter_with_template(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "# Cover Letter\n\nDear Team,\n\nI am excited to apply."}}
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_cover_letter(
        "Engineer", "Co", "Job description", "CV text", template_text="Template content"
    )
    assert "# Cover Letter" in result
    assert "Dear Team," in result


def test_llm_cover_letter_without_template(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "# Cover Letter\n\nDear Hiring Manager,\n\nI am writing."}}
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_cover_letter("Engineer", "Co", "Job description", "CV text", template_text="")
    assert "# Cover Letter" in result
    assert "Dear Hiring Manager," in result


def test_llm_cover_letter_strips_markdown_fences(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "```markdown\n# Cover Letter\n\nDear Team,\n\nI am excited.\n```"
                }
            }
        ]
    }
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    result = _llm_cover_letter("Engineer", "Co", "Desc", "CV", template_text="")
    assert "# Cover Letter" in result
    assert "```" not in result


def test_generate_cover_letter_job_not_found(db_session):
    state = {}
    generate_cover_letter(9999, state)
    assert "not found" in state["message"]


def test_generate_cover_letter_no_template(mock_httpx_md, db_session, monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cover_letter.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr(
        "app.services.cover_letter.settings.cover_letter_template_path",
        str(tmp_path / "nonexistent.md"),
    )
    monkeypatch.setattr("app.services.cover_letter.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_cl_no_tmpl",
        title="Software Engineer",
        company="Tech Corp",
        description="Python developer needed.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    generate_cover_letter(job.id, state, use_template=False)
    db_session.refresh(job)
    assert job.cover_letter_path is not None
    assert "Cover letter" in state["message"]


def test_generate_cover_letter_with_template(mock_httpx_md, db_session, monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    tmpl_path = tmp_path / "cover_letter.md"
    tmpl_path.write_text("# Template\n\nDear [Name],\n\n{{body}}\n", encoding="utf-8")
    monkeypatch.setattr("app.services.cover_letter.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr(
        "app.services.cover_letter.settings.cover_letter_template_path", str(tmpl_path)
    )
    monkeypatch.setattr("app.services.cover_letter.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_cl_tmpl",
        title="Data Scientist",
        company="AI Corp",
        description="ML experience required.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    generate_cover_letter(job.id, state, use_template=True)
    db_session.refresh(job)
    assert job.cover_letter_path is not None
    assert (
        "cover letter saved" in state["message"].lower()
        or "cover letter" in state["message"].lower()
    )


def test_generate_cover_letter_conversions_disabled(
    mock_httpx_md, db_session, monkeypatch, tmp_path
):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cover_letter.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr(
        "app.services.cover_letter.settings.cover_letter_template_path",
        str(tmp_path / "nonexistent.md"),
    )
    monkeypatch.setattr("app.services.cover_letter.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_cl_disabled",
        title="Engineer",
        company="Co",
        description="Description.",
    )
    db_session.add(job)
    db_session.commit()
    db_session.add(Setting(key="convert_cl_pdf", value="0"))
    db_session.add(Setting(key="convert_cl_docx", value="0"))
    db_session.commit()
    state = {}
    generate_cover_letter(job.id, state, use_template=False)
    db_session.refresh(job)
    assert job.cover_letter_path is not None
    assert "conversions disabled" in state["message"]


def test_generate_cover_letter_template_not_found(mock_httpx_md, db_session, monkeypatch, tmp_path):
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.cover_letter.settings.cv_tex_path", str(cv_path))
    monkeypatch.setattr(
        "app.services.cover_letter.settings.cover_letter_template_path", "/nonexistent/template.md"
    )
    monkeypatch.setattr("app.services.cover_letter.settings.output_dir", str(tmp_path))
    job = Job(
        linkedin_job_id="test_cl_no_tmpl_file",
        title="Engineer",
        company="Co",
        description="Desc.",
    )
    db_session.add(job)
    db_session.commit()
    state = {}
    generate_cover_letter(job.id, state, use_template=True)
    assert "No template found" in state["message"] or "cover letter" in state["message"].lower()
