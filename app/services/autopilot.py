import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import AutoPilotRun, Job, JobStatus, SearchQuery, Setting

logger = logging.getLogger("apply-buddy.autopilot")

AUTOPILOT_SETTINGS = {
    "autopilot_min_score": "70",
    "autopilot_tailor_cv": "1",
    "autopilot_cover_letter": "1",
    "autopilot_use_template": "1",
}


def _load_autopilot_setting(key: str, default: str) -> str:
    try:
        with Session(engine) as session:
            setting = session.get(Setting, key)
            if setting and setting.value:
                return setting.value
    except Exception:
        pass
    return default


def run_autopilot(state: dict[str, Any]) -> None:
    run_id = state.get("run_id")
    try:
        min_score = int(_load_autopilot_setting("autopilot_min_score", "70"))
        tailor_cv = _load_autopilot_setting("autopilot_tailor_cv", "1") == "1"
        cover_letter = _load_autopilot_setting("autopilot_cover_letter", "1") == "1"
        use_template = _load_autopilot_setting("autopilot_use_template", "1") == "1"

        # Phase 1: Scrape
        if state.get("skip_fetch"):
            state["message"] = "Skipping fetch, using existing jobs"
        else:
            state["phase"] = "scraping"
            state["message"] = "Starting scrape..."
            _run_scrape_phase(state)

        # Phase 2: Score
        state["phase"] = "scoring"
        state["message"] = "Starting scoring..."
        _run_score_phase(state)

        # Phase 3: Process high-fit jobs
        state["phase"] = "processing"
        state["message"] = "Processing high-fit jobs..."
        _run_process_phase(state, min_score, tailor_cv, cover_letter, use_template)

        # Phase 4: Finalize
        state["phase"] = "done"
        state["message"] = "Auto-Pilot complete"
        state["running"] = False

        with Session(engine) as session:
            if run_id is not None:
                run = session.get(AutoPilotRun, run_id)
                if run:
                    run.status = "completed"
                    run.completed_at = datetime.now(UTC)
                    run.jobs_scraped = state.get("scraped_count", 0)
                    run.jobs_scored = state.get("scored_count", 0)
                    run.jobs_tailored = state.get("tailored_count", 0)
                    run.jobs_cover_letter = state.get("cl_count", 0)
                    run.errors = state.get("errors", 0)
                    run.message = state["message"]
                    session.add(run)
                    session.commit()

    except Exception as e:
        logger.exception("Auto-Pilot failed: %s", e)
        state["phase"] = "error"
        state["message"] = f"Auto-Pilot error: {e}"
        state["running"] = False
        with Session(engine) as session:
            if run_id is not None:
                run = session.get(AutoPilotRun, run_id)
                if run:
                    run.status = "failed"
                    run.completed_at = datetime.now(UTC)
                    run.message = str(e)
                    session.add(run)
                    session.commit()


def _run_scrape_phase(state: dict[str, Any]) -> None:
    import threading

    from app.services.scraper import scrape_jobs

    with Session(engine) as session:
        queries = session.exec(select(SearchQuery).where(SearchQuery.enabled)).all()

    if not queries:
        state["message"] = "No enabled search queries, skipping scrape"
        state["scraped_count"] = 0
        return

    scrape_state = {"running": True, "total": 0, "current": 0, "errors": 0, "message": ""}
    t = threading.Thread(target=scrape_jobs, args=(queries, scrape_state), daemon=True)
    t.start()
    while scrape_state.get("running"):
        state["message"] = scrape_state.get("message", "")
        state["current"] = scrape_state.get("current", 0)
        state["total"] = scrape_state.get("total", 0)
        state["errors"] = scrape_state.get("errors", 0)
        time.sleep(0.5)
    t.join()

    state["scraped_count"] = scrape_state.get("current", 0)
    state["errors"] = (state.get("errors", 0) or 0) + (scrape_state.get("errors", 0) or 0)
    state["message"] = f"Scraped {state['scraped_count']} job listings"


def _run_score_phase(state: dict[str, Any]) -> None:
    import threading

    from app.services.matcher import score_all_new_jobs

    score_state = {"running": True, "total": 0, "current": 0, "errors": 0, "message": ""}
    t = threading.Thread(
        target=score_all_new_jobs, args=(score_state,), kwargs={"force_rescore": False}, daemon=True
    )
    t.start()
    while score_state.get("running"):
        state["message"] = score_state.get("message", "")
        state["current"] = score_state.get("current", 0)
        state["total"] = score_state.get("total", 0)
        state["errors"] = (state.get("errors", 0) or 0) + (score_state.get("errors", 0) or 0)
        time.sleep(0.5)
    t.join()

    state["scored_count"] = score_state.get("current", 0)
    state["errors"] = (state.get("errors", 0) or 0) + (score_state.get("errors", 0) or 0)
    state["message"] = f"Scoring finished: {state['scored_count']} jobs scored"


def _run_process_phase(
    state: dict[str, Any],
    min_score: int,
    tailor_cv: bool,
    cover_letter: bool,
    use_template: bool,
) -> None:
    from app.services.cover_letter import generate_cover_letter
    from app.services.cv_tailor import tailor_cv_for_job

    with Session(engine) as session:
        jobs = session.exec(
            select(Job).where(
                Job.status == JobStatus.new,
                Job.fit_score.isnot(None),
                Job.fit_score >= min_score,
                Job.autopilot_processed_at.is_(None),
            )
        ).all()

    if not jobs:
        state["message"] = "No high-fit jobs to process"
        state["tailored_count"] = 0
        state["cl_count"] = 0
        return

    state["total"] = len(jobs)
    state["current"] = 0
    state["tailored_count"] = 0
    state["cl_count"] = 0

    def _process_one_job(job: Job) -> tuple[int, bool, bool]:
        cv_ok = False
        cl_ok = False
        job_errors = 0
        if tailor_cv:
            sub_state = {"running": True, "message": ""}
            try:
                tailor_cv_for_job(job.id, sub_state)
                msg = sub_state.get("message", "")
                if msg and "error" not in msg.lower():
                    cv_ok = True
                else:
                    job_errors += 1
            except Exception as e:
                logger.error("CV tailoring failed for job %s: %s", job.id, e)
                job_errors += 1

        if cover_letter:
            sub_state = {"running": True, "message": ""}
            try:
                generate_cover_letter(job.id, sub_state, use_template=use_template)
                msg = sub_state.get("message", "")
                if msg and "error" not in msg.lower():
                    cl_ok = True
                else:
                    job_errors += 1
            except Exception as e:
                logger.error("Cover letter failed for job %s: %s", job.id, e)
                job_errors += 1

        with Session(engine) as session:
            db_job = session.get(Job, job.id)
            if db_job:
                db_job.autopilot_processed_at = datetime.now(UTC)
                if cv_ok or cl_ok or (not tailor_cv and not cover_letter):
                    db_job.status = JobStatus.ready
                session.add(db_job)
                session.commit()

        return job_errors, cv_ok, cl_ok

    max_conc = settings.llm_max_concurrency
    with ThreadPoolExecutor(max_workers=max_conc) as executor:
        future_to_job = {executor.submit(_process_one_job, job): job for job in jobs}
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                job_errors, cv_ok, cl_ok = future.result()
                if cv_ok:
                    state["tailored_count"] += 1
                if cl_ok:
                    state["cl_count"] += 1
                state["current"] += 1
                state["errors"] = (state.get("errors", 0) or 0) + job_errors
                state["message"] = (
                    f"Processed {state['current']}/{state['total']}: {job.title} at {job.company}"
                )
            except Exception as e:
                logger.error("Process failed for job %s: %s", job.id, e)
                state["current"] += 1
                state["errors"] = (state.get("errors", 0) or 0) + 1

    state["message"] = (
        f"Processed {len(jobs)} jobs: {state['tailored_count']} CVs tailored, {state['cl_count']} cover letters generated"
    )
