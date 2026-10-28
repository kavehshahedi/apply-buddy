import json

from sqlmodel import delete

from app.models import Job, JobStatus, SearchQuery, Setting
from app.services.llm import LLMError
from app.services.matcher import score_all_new_jobs
from app.services.triage import (
    DEFAULT_TRIAGE_PROMPT,
    TRIAGE_BATCH_SIZE,
    TRIAGE_REASON_PREFIX,
    triage_new_jobs,
)


def _reset(db_session):
    db_session.exec(delete(Job))
    db_session.exec(delete(SearchQuery))
    db_session.commit()


def _add_job(db_session, linkedin_id, title, **kwargs):
    job = Job(linkedin_job_id=linkedin_id, title=title, company="Co", description="Desc", **kwargs)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _fake_llm(monkeypatch, decide):
    """Answer each triage call with decide(posting) -> keep, recording every batch and prompt."""
    batches, prompts = [], []

    def fake(messages, response_format=None, model=None):
        prompt = messages[1]["content"]
        jobs = json.loads(prompt.split("truncated):\n")[1].split("\n\nReturn JSON")[0])
        batches.append(jobs)
        prompts.append(prompt)
        return json.dumps(
            {"results": [{"id": j["id"], "keep": decide(j), "reason": "off-field"} for j in jobs]}
        )

    monkeypatch.setattr("app.services.triage.chat_completion", fake)
    return batches, prompts


def test_triage_archives_dropped_and_keeps_rest(db_session, monkeypatch):
    _reset(db_session)
    keep = _add_job(db_session, "t1", "Project Coordinator")
    drop = _add_job(db_session, "t2", "Forklift Operator")
    _fake_llm(monkeypatch, lambda j: j["title"] != "Forklift Operator")

    state = {"errors": 0}
    assert triage_new_jobs("cv", state) == 1

    db_session.refresh(keep)
    db_session.refresh(drop)
    assert keep.status == JobStatus.new and keep.fit_reason is None
    assert drop.status == JobStatus.archived
    assert drop.fit_reason == TRIAGE_REASON_PREFIX + "off-field"
    assert drop.fit_score is None


def test_triage_sends_queries_snippets_and_batches(db_session, monkeypatch):
    _reset(db_session)
    db_session.add(SearchQuery(keywords="events coordinator", enabled=True))
    db_session.add(SearchQuery(keywords="disabled query", enabled=False))
    db_session.commit()
    for i in range(TRIAGE_BATCH_SIZE + 1):
        _add_job(db_session, f"b{i}", f"Job {i}")
    batches, prompts = _fake_llm(monkeypatch, lambda j: True)

    triage_new_jobs("cv", {"errors": 0})

    assert sorted(len(b) for b in batches) == [1, TRIAGE_BATCH_SIZE]
    assert all("- events coordinator" in p and "disabled query" not in p for p in prompts)


def test_triage_skips_scored_archived_and_restored_jobs(db_session, monkeypatch):
    _reset(db_session)
    _add_job(db_session, "s1", "Scored", fit_score=50)
    _add_job(db_session, "s2", "Archived", status=JobStatus.archived)
    _add_job(db_session, "s3", "Restored by user", fit_reason=TRIAGE_REASON_PREFIX + "x")
    batches, _ = _fake_llm(monkeypatch, lambda j: False)

    assert triage_new_jobs("cv", {"errors": 0}) == 0
    assert batches == []


def test_triage_keeps_jobs_on_llm_error_or_bad_answer(db_session, monkeypatch):
    _reset(db_session)
    job = _add_job(db_session, "e1", "Anything")
    state = {"errors": 0}

    def boom(*args, **kwargs):
        raise LLMError("down")

    monkeypatch.setattr("app.services.triage.chat_completion", boom)
    assert triage_new_jobs("cv", state) == 0
    assert state["errors"] == 1

    # Unknown ids, missing keep flags and non-JSON all leave the job untouched
    for answer in (
        '{"results": [{"id": 999999, "keep": false}]}',
        f'{{"results": [{{"id": {job.id}, "reason": "no flag"}}]}}',
        "not json",
    ):
        monkeypatch.setattr("app.services.triage.chat_completion", lambda *a, ans=answer, **k: ans)
        triage_new_jobs("cv", state)

    db_session.refresh(job)
    assert job.status == JobStatus.new


def test_score_all_new_jobs_triages_before_scoring(mock_httpx, db_session, monkeypatch):
    _reset(db_session)
    monkeypatch.setattr(
        "app.services.matcher.read_cv_text",
        lambda: "\\documentclass{article}\\begin{document}Test CV\\end{document}",
    )
    keep = _add_job(db_session, "m1", "Project Coordinator")
    drop = _add_job(db_session, "m2", "Forklift Operator")
    _fake_llm(monkeypatch, lambda j: j["title"] != "Forklift Operator")

    score_all_new_jobs({"errors": 0})

    db_session.refresh(keep)
    db_session.refresh(drop)
    assert keep.fit_score == 85
    assert drop.status == JobStatus.archived and drop.fit_score is None


def test_score_all_new_jobs_skips_triage_when_disabled(mock_httpx, db_session, monkeypatch):
    _reset(db_session)
    existing = db_session.get(Setting, "triage_enabled")
    if existing:
        existing.value = "0"
    else:
        db_session.add(Setting(key="triage_enabled", value="0"))
    db_session.commit()
    monkeypatch.setattr("app.services.matcher.read_cv_text", lambda: None)
    _add_job(db_session, "d1", "Forklift Operator")
    batches, _ = _fake_llm(monkeypatch, lambda j: False)

    score_all_new_jobs({"errors": 0})

    assert batches == []


def test_default_triage_prompt_formats():
    prompt = DEFAULT_TRIAGE_PROMPT.format(queries="q", cv_plain="c", jobs="[]")
    assert '{"results": [{"id"' in prompt
