import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/manual-fetch", tags=["manual-fetch"])

_manual_state = {"running": False, "total": 0, "current": 0, "errors": 0, "message": ""}


class ManualFetchRequest(BaseModel):
    url: str


@router.post("/run")
async def run_manual_fetch(
    body: ManualFetchRequest,
    background_tasks: BackgroundTasks,
):
    url = body.url.strip()

    if not url.startswith("https://www.linkedin.com/jobs/view/"):
        return JSONResponse(
            {"error": "Invalid LinkedIn job URL. Must start with https://www.linkedin.com/jobs/view/"},
            status_code=400,
        )

    if _manual_state["running"]:
        return JSONResponse({"error": "Manual fetch already running"}, status_code=409)

    _manual_state["running"] = True
    _manual_state["total"] = 0
    _manual_state["current"] = 0
    _manual_state["errors"] = 0
    _manual_state["message"] = f"Starting fetch for {url}..."
    background_tasks.add_task(_run_manual_fetch_impl, url)
    return JSONResponse({"ok": True})


async def _run_manual_fetch_impl(url: str):
    from app.services.scraper import scrape_single_job

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, scrape_single_job, url, _manual_state)
    finally:
        _manual_state["running"] = False


@router.get("/progress")
async def manual_fetch_progress():
    return JSONResponse(_manual_state)