import contextlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import AutoPilotRun, Job, JobStatus

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
async def run_autopilot(background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    if _autopilot_state["running"]:
        return JSONResponse({"error": "Auto-Pilot already running"}, status_code=409)

    from app.models import SearchQuery

    queries_exist = session.exec(select(SearchQuery).where(SearchQuery.enabled)).first()
    if not queries_exist:
        return JSONResponse({"error": "No enabled search queries"}, status_code=400)

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

    background_tasks.add_task(_run_autopilot_impl)
    return JSONResponse({"ok": True})


async def _run_autopilot_impl():
    from app.services.autopilot import run_autopilot

    try:
        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_autopilot, _autopilot_state)
    finally:
        pass


@router.get("/progress")
async def autopilot_progress():
    return JSONResponse(_autopilot_state)


@router.get("/queue", response_class=HTMLResponse)
async def autopilot_queue(request: Request, session: Session = Depends(get_session)):
    min_score = 70
    from app.models import Setting

    setting = session.get(Setting, "autopilot_min_score")
    if setting and setting.value:
        with contextlib.suppress(ValueError, TypeError):
            min_score = int(setting.value)

    jobs = session.exec(
        select(Job)
        .where(
            Job.status == JobStatus.ready,
            Job.fit_score.isnot(None),
            Job.fit_score >= min_score,
        )
        .order_by(Job.fit_score.desc())
    ).all()

    return request.app.state.templates.TemplateResponse(
        request,
        "autopilot_queue.html",
        {
            "jobs": jobs,
            "min_score": min_score,
        },
    )


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
