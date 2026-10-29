from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import InterviewSession, Job, JobStatus

router = APIRouter(prefix="/applied", tags=["applied"])

GHOSTED_AFTER = timedelta(days=30)

# id: (label, column, color token, tooltip hint). Order within a column = top-to-bottom order.
FLOW_NODES = {
    "applied": ("Applied", 0, "--status-applied", "Every application sent"),
    "interview": ("Interview", 1, "--purple", "Reached an interview"),
    "awaiting": ("Awaiting", 1, "--status-awaiting", "Applied in the last 30 days"),
    "ghosted": ("No response", 1, "--status-ghosted", "Silent for 30+ days"),
    "rejected": ("Rejected", 1, "--danger", "Rejected without an interview"),
    "offer": ("Offer", 2, "--success", "Received an offer"),
    "interviewing": ("In progress", 2, "--purple", "Still interviewing"),
    "interview_rejected": ("Rejected", 2, "--danger", "Rejected after interviewing"),
    "accepted": ("Accepted", 3, "--status-accepted", "Offer accepted"),
    "offer_pending": ("Deciding", 3, "--success", "Offer on the table"),
    "declined": ("Declined", 3, "--danger", "Offer declined or withdrawn"),
}


def flow_path(job: Job, interviewed: bool, now: datetime) -> list[str]:
    """Node ids a job passes through, from 'applied' to its terminal node."""
    offered = job.status in (JobStatus.offer, JobStatus.accepted) or job.offered_at is not None
    interviewed = (
        offered
        or interviewed
        or job.status == JobStatus.interview
        or job.interviewed_at is not None
    )
    path = ["applied"] + (["interview"] if interviewed else []) + (["offer"] if offered else [])
    stage = path[-1]
    if job.status == JobStatus.accepted:
        return path + ["accepted"]
    if job.status == JobStatus.rejected:
        return path + [
            {"applied": "rejected", "interview": "interview_rejected", "offer": "declined"}[stage]
        ]
    if stage == "applied":
        sent = job.applied_at or job.updated_at
        if sent.tzinfo is None:
            sent = sent.replace(tzinfo=UTC)
        return path + ["ghosted" if now - sent > GHOSTED_AFTER else "awaiting"]
    return path + [{"interview": "interviewing", "offer": "offer_pending"}[stage]]


def build_flow(
    jobs: list[Job], interviewed_ids: set[int], now: datetime
) -> tuple[dict, dict[int | None, list[str]]]:
    paths = {job.id: flow_path(job, job.id in interviewed_ids, now) for job in jobs}
    nodes = Counter(n for p in paths.values() for n in p)
    links = Counter((a, b) for p in paths.values() for a, b in pairwise(p))
    flow = {
        "total": len(jobs),
        "nodes": [
            {
                "id": nid,
                "label": label,
                "col": col,
                "color": color,
                "hint": hint,
                "value": nodes[nid],
            }
            for nid, (label, col, color, hint) in FLOW_NODES.items()
            if nodes[nid]
        ],
        "links": [{"source": a, "target": b, "value": v} for (a, b), v in links.items()],
    }
    return flow, paths


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
    interviewed_ids = set(session.exec(select(InterviewSession.job_id).distinct()).all())
    flow, paths = build_flow(jobs, interviewed_ids, datetime.now(UTC))
    return request.app.state.templates.TemplateResponse(
        request, "applied.html", {"jobs": jobs, "flow": flow, "paths": paths}
    )
