import asyncio
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from app.db import get_session
from app.models import SearchQuery

router = APIRouter(prefix="/scrape", tags=["scrape"])

_scrape_state = {"running": False, "total": 0, "current": 0, "errors": 0, "message": ""}


@router.post("/run")
async def run_scrape(
    background_tasks: BackgroundTasks, session: Session = Depends(get_session)
):
    if _scrape_state["running"]:
        return JSONResponse({"error": "Scrape already running"}, status_code=409)
    queries = session.exec(select(SearchQuery).where(SearchQuery.enabled == True)).all()
    if not queries:
        return JSONResponse({"error": "No enabled search queries"}, status_code=400)
    _scrape_state["running"] = True
    _scrape_state["total"] = 0
    _scrape_state["current"] = 0
    _scrape_state["errors"] = 0
    _scrape_state["message"] = "Starting scrape..."
    background_tasks.add_task(_run_scrape_impl, queries)
    return JSONResponse({"ok": True})


async def _run_scrape_impl(queries):
    from app.services.scraper import scrape_jobs

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, scrape_jobs, queries, _scrape_state)
    finally:
        _scrape_state["running"] = False
        _scrape_state["message"] = "Scrape complete"


@router.get("/progress")
async def scrape_progress():
    return JSONResponse(_scrape_state)
