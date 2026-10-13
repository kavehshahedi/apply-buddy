from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.db import get_session
from app.models import Job
from app.schemas import ChatRequest
from app.services.job_chat import ask
from app.services.llm import LLMError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{job_id}")
def chat(job_id: int, data: ChatRequest, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    history = [m.model_dump() for m in data.messages]
    try:
        reply = ask(job, history, data.cv, data.cover_letter)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return JSONResponse({"reply": reply})
