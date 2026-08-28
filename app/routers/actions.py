from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import Job

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

    _action_state[str(job_id)] = {
        "running": True,
        "message": "Starting scoring...",
        "action": "score-fit",
        "cv_source": cv_source,
    }
    background_tasks.add_task(_run_score_fit, job_id, cv_path)
    return JSONResponse({"ok": True})


def _run_score_fit(job_id: int, cv_path: str | None = None):
    from app.services.matcher import score_single_job

    state = _action_state.get(str(job_id))
    try:
        score_single_job(job_id, state, cv_path)
        if state:
            state["message"] = "Scoring complete"
    except Exception as e:
        if state:
            state["message"] = f"Error: {e}"
    finally:
        if state:
            state["running"] = False


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
    background_tasks.add_task(_run_tailor_cv, job_id)
    return JSONResponse({"ok": True})


def _run_tailor_cv(job_id: int):
    from app.services.cv_tailor import tailor_cv_for_job

    state = _action_state.get(str(job_id))
    try:
        tailor_cv_for_job(job_id, state) if state else tailor_cv_for_job(job_id)
        if state:
            state["message"] = "CV tailored successfully"
    except Exception as e:
        if state:
            state["message"] = f"Error: {e}"
    finally:
        if state:
            state["running"] = False


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
    background_tasks.add_task(_run_cover_letter, job_id, use_template)
    return JSONResponse({"ok": True})


def _run_cover_letter(job_id: int, use_template: bool = True):
    from app.services.cover_letter import generate_cover_letter

    state = _action_state.get(str(job_id))
    try:
        if state:
            generate_cover_letter(job_id, state, use_template=use_template)
        else:
            generate_cover_letter(job_id, use_template=use_template)
    except Exception as e:
        if state:
            state["message"] = f"Error: {e}"
    finally:
        if state:
            state["running"] = False


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
