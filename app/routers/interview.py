import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import InterviewSession, Job
from app.schemas import InterviewAnswerSubmit, InterviewSessionCreate

logger = logging.getLogger("apply-buddy.interview")

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sort_gaps_by_severity(gaps: list) -> list:
    return sorted(gaps, key=lambda g: _SEVERITY_ORDER.get(g.get("gap_severity", "low"), 2))


router = APIRouter(prefix="/interview", tags=["interview"])

_interview_generation_state: dict = {}
_gen_locks: dict[str, asyncio.Lock] = {}


@router.get("/{job_id}", response_class=HTMLResponse)
def interview_page(request: Request, job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing_session = session.exec(
        select(InterviewSession)
        .where(InterviewSession.job_id == job_id)
        .order_by(InterviewSession.id.desc())
    ).first()

    prep_questions = existing_session.prep_questions if existing_session else []
    prep_skills_gap = (
        _sort_gaps_by_severity(existing_session.prep_skills_gap) if existing_session else []
    )

    active_session = None
    if existing_session and existing_session.status == "in_progress":
        active_session = existing_session

    return request.app.state.templates.TemplateResponse(
        request,
        "interview.html",
        {
            "job": job,
            "prep_questions": prep_questions,
            "prep_skills_gap": prep_skills_gap,
            "active_session": active_session,
        },
    )


@router.post("/{job_id}/generate")
async def generate_prep(
    job_id: int, background_tasks: BackgroundTasks, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    key = str(job_id)
    lock = _gen_locks.setdefault(key, asyncio.Lock())
    async with lock:
        if key in _interview_generation_state and _interview_generation_state[key].get("running"):
            raise HTTPException(status_code=409, detail="Generation already running")

        _interview_generation_state[key] = {"running": True, "message": "Starting generation..."}
        background_tasks.add_task(_run_generate_prep, job_id)
    return JSONResponse({"ok": True})


def _run_generate_prep(job_id: int):
    from app.services.interview_prep import generate_prep_pack

    state = _interview_generation_state.get(str(job_id))
    try:
        generate_prep_pack(job_id, state)
    except Exception as e:
        if state:
            state["message"] = f"Error: {e}"
    finally:
        if state:
            state["running"] = False


@router.get("/{job_id}/progress")
def interview_progress(job_id: int):
    state = _interview_generation_state.get(str(job_id), {"running": False, "message": ""})
    return JSONResponse(state)


@router.post("/{job_id}/session")
def start_session(
    job_id: int,
    data: InterviewSessionCreate,
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.services.interview_prep import start_session as _start_session

    try:
        session_obj = _start_session(job_id, data.total_questions, db_session=session)
        return JSONResponse(
            {
                "session_id": session_obj.id,
                "total_questions": session_obj.total_questions,
                "current_question": session_obj.current_question,
                "questions": session_obj.questions,
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{job_id}/session/{session_id}/answer")
def submit_answer(
    job_id: int,
    session_id: int,
    data: InterviewAnswerSubmit,
    db_session: Session = Depends(get_session),
):
    job = db_session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    session_obj = db_session.get(InterviewSession, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.job_id != job_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this job")

    from app.services.interview_prep import submit_answer as _submit_answer

    try:
        result = _submit_answer(session_id, data.answer, db_session=db_session)
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to submit answer")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/{job_id}/session/{session_id}")
def get_session_state(
    job_id: int,
    session_id: int,
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    session_obj = session.get(InterviewSession, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_obj.job_id != job_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this job")

    return JSONResponse(
        {
            "session_id": session_obj.id,
            "status": session_obj.status,
            "total_questions": session_obj.total_questions,
            "current_question": session_obj.current_question,
            "questions": session_obj.questions or [],
            "user_answers": session_obj.user_answers or [],
            "feedback": session_obj.feedback or [],
            "overall_summary": session_obj.overall_summary,
        }
    )
