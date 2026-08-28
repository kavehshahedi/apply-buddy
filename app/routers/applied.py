from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Job, JobStatus

router = APIRouter(prefix="/applied", tags=["applied"])


@router.get("/", response_class=HTMLResponse)
async def applied_board(request: Request, session: Session = Depends(get_session)):
    jobs = session.exec(
        select(Job)
        .where(
            Job.status.in_(
                [
                    JobStatus.applied,
                    JobStatus.interview,
                    JobStatus.rejected,
                    JobStatus.offer,
                    JobStatus.accepted,
                ]
            )
        )
        .order_by(Job.updated_at.desc())
    ).all()
    return request.app.state.templates.TemplateResponse(
        "applied.html", {"request": request, "jobs": jobs}
    )
