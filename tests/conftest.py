import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["LLM_BASE_URL"] = "http://test:1234/v1"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_MODEL"] = "test-model"
os.environ["LLM_TEMPERATURE"] = "0.5"
os.environ["LLM_PROVIDER"] = "openai"
os.environ["OUTPUT_DIR"] = os.path.join(_tmp_dir, "output")

from app.config import settings
from app.db import get_session
from app.main import app
from app.models import Job, JobStatus, SearchQuery, Setting


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    yield


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def _patch_engine_and_state(test_engine):
    import app.db as db_mod
    import app.routers.actions as actions_router
    import app.routers.manual_fetch as manual_fetch_router
    import app.routers.scrape as scrape_router
    import app.services.cover_letter as cl_mod
    import app.services.cv_tailor as cv_mod
    import app.services.matcher as matcher_mod
    import app.services.scraper as scraper_mod

    originals = {}
    for mod in [db_mod, matcher_mod, cv_mod, cl_mod, scraper_mod]:
        originals[mod] = mod.engine
        mod.engine = test_engine

    scrape_router._scrape_state["running"] = False
    scrape_router._scrape_state["total"] = 0
    scrape_router._scrape_state["current"] = 0
    scrape_router._scrape_state["errors"] = 0
    scrape_router._scrape_state["message"] = ""

    manual_fetch_router._manual_state["running"] = False
    manual_fetch_router._manual_state["total"] = 0
    manual_fetch_router._manual_state["current"] = 0
    manual_fetch_router._manual_state["errors"] = 0
    manual_fetch_router._manual_state["message"] = ""

    actions_router._score_state["running"] = False
    actions_router._score_state["total"] = 0
    actions_router._score_state["current"] = 0
    actions_router._score_state["errors"] = 0
    actions_router._score_state["message"] = ""

    actions_router._action_state.clear()

    with Session(test_engine) as session:
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

    yield

    for mod, orig in originals.items():
        if hasattr(mod, "engine"):
            mod.engine = orig


@pytest.fixture(autouse=True)
def _override_dependency(test_engine):
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def sample_job_data():
    return {
        "linkedin_job_id": "test_123",
        "title": "Software Engineer",
        "company": "Test Corp",
        "location": "Remote",
        "link": "https://linkedin.com/jobs/view/123",
        "apply_link": "https://apply.test.com",
        "description": "We are looking for a software engineer with Python experience.",
        "date_posted": "3 days ago",
        "date_posted_dt": datetime.now(UTC) - timedelta(days=3),
        "status": JobStatus.new,
    }


@pytest.fixture
def sample_job(db_session, sample_job_data):
    job = Job(**sample_job_data)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def sample_query_data():
    return {
        "keywords": "software engineer",
        "locations": '["Remote"]',
        "time_filter": "any",
        "limit": 25,
        "enabled": True,
    }


@pytest.fixture
def sample_query(db_session, sample_query_data):
    query = SearchQuery(**sample_query_data)
    db_session.add(query)
    db_session.commit()
    db_session.refresh(query)
    return query


@pytest.fixture
def sample_setting(db_session):
    setting = Setting(key="test_key", value="test_value")
    db_session.add(setting)
    db_session.commit()
    db_session.refresh(setting)
    return setting


@pytest.fixture
def mock_httpx(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"fit_score": 85, "reason": "Great match", "cv_change_recommended": false, "cv_change_reason": ""}'
                }
            }
        ]
    }
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("httpx.post", mock_post)
    return mock_post


@pytest.fixture
def mock_httpx_tex(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "\\documentclass{article}\n\\begin{document}\nTailored CV\n\\end{document}"
                }
            }
        ]
    }
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("httpx.post", mock_post)
    return mock_post


@pytest.fixture
def mock_httpx_md(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "# Cover Letter\n\nDear Hiring Manager,\n\nI am writing to apply..."
                }
            }
        ]
    }
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("httpx.post", mock_post)
    return mock_post


@pytest.fixture
def mock_latex_available(monkeypatch):
    monkeypatch.setattr("app.services.compile.latex_available", lambda: True)
    monkeypatch.setattr("app.services.cv_tailor.latex_available", lambda: True)


@pytest.fixture
def mock_latex_unavailable(monkeypatch):
    monkeypatch.setattr("app.services.compile.latex_available", lambda: False)
    monkeypatch.setattr("app.services.cv_tailor.latex_available", lambda: False)


@pytest.fixture
def mock_pandoc_available(monkeypatch):
    monkeypatch.setattr("app.services.compile.pandoc_available", lambda: True)


@pytest.fixture
def mock_pandoc_unavailable(monkeypatch):
    monkeypatch.setattr("app.services.compile.pandoc_available", lambda: False)


@pytest.fixture
def mock_subprocess_success(monkeypatch):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    monkeypatch.setattr("subprocess.run", mock_result)


@pytest.fixture
def mock_subprocess_failure(monkeypatch):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "error output"
    mock_result.stderr = "error details"
    monkeypatch.setattr("subprocess.run", mock_result)


@pytest.fixture
def mock_shutil_which(monkeypatch):
    def _which(name, **kwargs):
        return f"/usr/bin/{name}"

    monkeypatch.setattr("shutil.which", _which)


@pytest.fixture
def mock_shutil_which_none(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name, **kwargs: None)


@pytest.fixture
def mock_scraper(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.scraper.scrape_jobs", mock)
    return mock


@pytest.fixture
def mock_scraper_single(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.scraper.scrape_single_job", mock)
    return mock


@pytest.fixture
def mock_matcher_batch(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.matcher.score_all_new_jobs", mock)
    return mock


@pytest.fixture
def mock_matcher_single(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.matcher.score_single_job", mock)
    return mock


@pytest.fixture
def mock_cv_tailor(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.cv_tailor.tailor_cv_for_job", mock)
    return mock


@pytest.fixture
def mock_cover_letter(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.cover_letter.generate_cover_letter", mock)
    return mock


@pytest.fixture
def temp_cv_file(monkeypatch):
    cv_dir = Path(_tmp_dir) / "cv"
    cv_dir.mkdir(parents=True, exist_ok=True)
    cv_path = cv_dir / "cv.tex"
    cv_path.write_text(
        "\\documentclass{article}\\begin{document}Test CV\\end{document}", encoding="utf-8"
    )
    monkeypatch.setattr(settings.__class__, "cv_tex_path", str(cv_path))
    monkeypatch.setattr(settings.__class__, "cv_tex_path_resolved", property(lambda s: cv_path))
    return cv_path


@pytest.fixture
def temp_cover_letter_template(monkeypatch):
    cl_dir = Path(_tmp_dir) / "cover-letter"
    cl_dir.mkdir(parents=True, exist_ok=True)
    cl_path = cl_dir / "cover_letter.md"
    cl_path.write_text("# Template\n\nDear [Name],\n\n{{body}}\n", encoding="utf-8")
    monkeypatch.setattr(settings.__class__, "cover_letter_template_path", str(cl_path))
    monkeypatch.setattr(
        settings.__class__, "cover_letter_template_path_resolved", property(lambda s: cl_path)
    )
    return cl_path
