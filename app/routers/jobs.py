import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from app.db import get_session
from app.models import Job, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_class=HTMLResponse)
async def job_list(
    request: Request,
    session: Session = Depends(get_session),
    sort: str = "date",
    order: str = "desc",
    min_score: int = 0,
    source: str = "all",
):
    query = select(Job).where(Job.status.in_([JobStatus.new, JobStatus.interested]))
    if min_score > 0:
        query = query.where(Job.fit_score >= min_score)
    if source == "linkedin":
        query = query.where(~Job.linkedin_job_id.like("manual%"))
    elif source == "manual":
        query = query.where(Job.linkedin_job_id.like("manual%"))
    if sort == "score":
        order_col = Job.fit_score
    elif sort == "scraped":
        order_col = Job.date_scraped
    else:
        order_col = Job.date_posted_dt
    order_fn = order_col.desc if order == "desc" else order_col.asc
    query = query.order_by(order_fn())
    jobs = session.exec(query).all()
    return request.app.state.templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "sort": sort,
            "order": order,
            "min_score": min_score,
            "source": source,
        },
    )


@router.get("/{job_id}", response_class=HTMLResponse)
async def job_detail(
    request: Request, job_id: int, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return request.app.state.templates.TemplateResponse(
        "job_detail.html", {"request": request, "job": job}
    )


@router.post("/manual", response_class=RedirectResponse)
async def create_manual_job(
    request: Request,
    title: str = Form(...),
    company: str = Form(...),
    description: str = Form(...),
    location: str = Form(""),
    link: str = Form(""),
    apply_link: str = Form(""),
    session: Session = Depends(get_session),
):
    job = Job(
        linkedin_job_id=f"manual_{uuid.uuid4().hex}",
        title=title,
        company=company,
        description=description,
        location=location,
        link=link,
        apply_link=apply_link or None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.post("/{job_id}/status")
async def update_job_status(
    job_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus(status)
    if notes:
        job.notes = notes
    if status == "applied" and job.applied_at is None:
        from datetime import datetime, timezone

        job.applied_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    return RedirectResponse(url="/jobs/", status_code=303)


@router.post("/{job_id}/delete")
async def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    session.delete(job)
    session.commit()
    return RedirectResponse(url="/jobs/", status_code=303)
