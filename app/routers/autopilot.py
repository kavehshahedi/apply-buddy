import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import nulls_last
from sqlmodel import Session, select

from app.db import get_session
from app.models import AutoPilotRun, Job, JobStatus, SearchQuery, Setting
from app.services.autopilot import run_autopilot as _run_autopilot_service

router = APIRouter(prefix="/autopilot", tags=["autopilot"])

_autopilot_state: dict[str, Any] = {
    "running": False,
    "phase": "",
    "total": 0,
    "current": 0,
    "errors": 0,
    "message": "",
    "run_id": None,
}


@router.post("/run")
async def run_autopilot(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    data: dict[str, Any] | None = None,
):
    if _autopilot_state["running"]:
        raise HTTPException(status_code=409, detail="Auto-Pilot already running")

    skip_fetch = (data or {}).get("skip_fetch", False)

    if not skip_fetch:
        queries_exist = session.exec(select(SearchQuery).where(SearchQuery.enabled)).first()
        if not queries_exist:
            raise HTTPException(status_code=400, detail="No enabled search queries")

    run = AutoPilotRun(
        started_at=datetime.now(UTC),
        status="running",
        message="Starting Auto-Pilot...",
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    _autopilot_state["running"] = True
    _autopilot_state["phase"] = "starting"
    _autopilot_state["total"] = 0
    _autopilot_state["current"] = 0
    _autopilot_state["errors"] = 0
    _autopilot_state["message"] = "Starting Auto-Pilot..."
    _autopilot_state["run_id"] = run.id
    _autopilot_state["skip_fetch"] = skip_fetch

    background_tasks.add_task(_run_autopilot_impl)
    return JSONResponse({"ok": True})


async def _run_autopilot_impl():
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_autopilot_service, _autopilot_state)
    finally:
        pass


@router.get("/progress")
async def autopilot_progress():
    return JSONResponse(_autopilot_state)


@router.get("/queue", response_class=HTMLResponse)
async def autopilot_queue(
    request: Request,
    session: Session = Depends(get_session),
    sort: str = "score",
    order: str = "desc",
    min_score: int = 0,
    files: str = "all",
    q: str = "",
):
    threshold = 70

    setting = session.get(Setting, "autopilot_min_score")
    if setting and setting.value:
        with contextlib.suppress(ValueError, TypeError):
            threshold = int(setting.value)
    # The queue only ever holds jobs above the Auto-Pilot threshold, so the filter can only raise it.
    min_score = max(min_score, threshold)

    order_col = {"posted": Job.date_posted_dt, "fetched": Job.date_scraped}.get(sort, Job.fit_score)
    jobs = session.exec(
        select(Job)
        .where(
            Job.status == JobStatus.ready,
            Job.fit_score.isnot(None),
            Job.fit_score >= min_score,
        )
        .order_by(nulls_last(order_col.asc() if order == "asc" else order_col.desc()))
    ).all()
    if files in ("complete", "incomplete"):
        jobs = [j for j in jobs if _has_all_files(j) == (files == "complete")]

    return request.app.state.templates.TemplateResponse(
        request,
        "autopilot_queue.html",
        {
            "jobs": jobs,
            "threshold": threshold,
            "min_score": min_score,
            "sort": sort,
            "order": order,
            "files": files,
            "q": q,
            "filtered": min_score > threshold or files in ("complete", "incomplete"),
        },
    )


def _has_all_files(job: Job) -> bool:
    has_cv = job.tailored_cv_path or job.tailored_cv_pdf_path
    has_cl = job.cover_letter_path or job.cover_letter_docx_path or job.cover_letter_pdf_path
    return bool(has_cv and has_cl)


@router.post("/reset")
async def reset_autopilot(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job).where(Job.status == JobStatus.ready)).all()
    count = 0
    for job in jobs:
        job.status = JobStatus.new
        job.autopilot_processed_at = None
        session.add(job)
        count += 1
    session.commit()
    return JSONResponse({"ok": True, "reset_count": count})


@router.get("/runs")
async def autopilot_runs(session: Session = Depends(get_session)):
    runs = session.exec(
        select(AutoPilotRun).order_by(AutoPilotRun.started_at.desc()).limit(20)
    ).all()
    return JSONResponse([r.model_dump() for r in runs])
