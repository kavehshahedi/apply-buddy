from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import Job
from app.services.utils import run_background_task

router = APIRouter(prefix="/actions", tags=["actions"])

_score_state = {"running": False, "total": 0, "current": 0, "errors": 0, "message": ""}
_action_state: dict = {}


@router.post("/score-fit")
async def score_fit(background_tasks: BackgroundTasks, force: bool = False):
    from app.services.matcher import score_all_new_jobs

    if _score_state["running"]:
        return JSONResponse({"error": "Scoring already running"}, status_code=409)
    _score_state["running"] = True
    _score_state["total"] = 0
    _score_state["current"] = 0
    _score_state["errors"] = 0
    _score_state["message"] = "Starting scoring..."
    background_tasks.add_task(score_all_new_jobs, _score_state, force_rescore=force)
    return JSONResponse({"ok": True})


@router.get("/score-progress")
async def score_progress():
    return JSONResponse(_score_state)


@router.post("/score-fit/{job_id}")
async def score_fit_single(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    cv_source: str = "reference",
):
    job = session.get(Job, job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if str(job_id) in _action_state and _action_state[str(job_id)].get("running"):
        return JSONResponse({"error": "Scoring already running for this job"}, status_code=409)

    cv_path = None
    if cv_source == "tailored" and job.tailored_cv_path:
        cv_path = str(Path(job.tailored_cv_path).resolve())

    from app.services.matcher import score_single_job

    _action_state[str(job_id)] = {
        "running": True,
        "message": "Starting scoring...",
        "action": "score-fit",
        "cv_source": cv_source,
    }
    state = _action_state.get(str(job_id))
    background_tasks.add_task(
        run_background_task,
        state,
        score_single_job,
        job_id,
        state,
        cv_path,
        success_message="Scoring complete",
    )
    return JSONResponse({"ok": True})


@router.post("/tailor-cv/{job_id}")
async def tailor_cv(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if str(job_id) in _action_state and _action_state[str(job_id)].get("running"):
        return JSONResponse({"error": "Action already running for this job"}, status_code=409)
    _action_state[str(job_id)] = {
        "running": True,
        "message": "Starting CV tailoring...",
        "action": "tailor-cv",
    }
    state = _action_state.get(str(job_id))
    from app.services.cv_tailor import tailor_cv_for_job

    background_tasks.add_task(
        run_background_task,
        state,
        tailor_cv_for_job,
        job_id,
        state,
        success_message="CV tailored successfully",
    )
    return JSONResponse({"ok": True})


@router.post("/cover-letter/{job_id}")
async def cover_letter(
    job_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    use_template: bool = True,
):
    job = session.get(Job, job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if str(job_id) in _action_state and _action_state[str(job_id)].get("running"):
        return JSONResponse({"error": "Action already running for this job"}, status_code=409)
    _action_state[str(job_id)] = {
        "running": True,
        "message": "Starting cover letter...",
        "action": "cover-letter",
        "use_template": use_template,
    }
    state = _action_state.get(str(job_id))
    from app.services.cover_letter import generate_cover_letter

    background_tasks.add_task(
        run_background_task,
        state,
        generate_cover_letter,
        job_id,
        state,
        success_message="Cover letter generated successfully",
        use_template=use_template,
    )
    return JSONResponse({"ok": True})


@router.get("/action-progress/{job_id}")
async def action_progress(job_id: int):
    state = _action_state.get(str(job_id), {"running": False, "message": ""})
    return JSONResponse(state)


@router.get("/download/{job_id}/{filename}")
async def download_file(job_id: int, filename: str):
    file_path = settings.output_path / str(job_id) / filename
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(str(file_path))
