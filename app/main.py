import contextlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.config import settings
from app.db import init_db


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Apply-Buddy", lifespan=lifespan)

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _timeago(dt: datetime) -> str:
    if dt is None:
        return ""
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = now - dt
    if diff < timedelta(seconds=0):
        return "just now"
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks}w ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


templates.env.filters["timeago"] = _timeago


def _to_eastern(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(ZoneInfo("America/New_York"))


templates.env.filters["to_eastern"] = _to_eastern


def _strftime(dt: datetime, fmt: str) -> str:
    if dt is None:
        return ""
    return dt.strftime(fmt)


templates.env.filters["strftime"] = _strftime


def _beautify_description(text: str) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    result = []
    buffer = []
    in_list = False

    _section_pattern = re.compile(
        r"^(about\s+the\s+job|company\s+description|job\s+description|"
        r"responsibilities|qualifications|requirements|benefits|overview|"
        r"what\s+(you['´`]?ll|we)\s+\w+|tasks|experience|education|"
        r"languages|skills|summary|key\s+\w+|why\s+.*)$",
        re.IGNORECASE,
    )
    _bullet_pattern = re.compile(r"^[\s]*[•\-\*▸→]\s+")
    _numbered_bullet = re.compile(r"^\s*\d+[.)]\s+")

    def is_section_header(s: str) -> bool:
        if len(s) > 60:
            return False
        if _section_pattern.match(s):
            return True
        if re.match(r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ\s\-/]{2,40}$", s) and s.strip().istitle():
            return True
        if re.match(r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ\s\-/]+:$", s):
            return True
        return False

    def flush_paragraph():
        nonlocal buffer
        if buffer:
            line = " ".join(buffer).strip()
            if line:
                result.append(f"<p>{line}</p>")
            buffer = []

    def flush_list():
        nonlocal in_list
        if in_list:
            result.append("</ul>")
            in_list = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if not line.strip():
            flush_list()
            flush_paragraph()
            continue

        stripped = line.strip()
        is_bullet = bool(_bullet_pattern.match(line) or _numbered_bullet.match(line))
        is_header = is_section_header(stripped)

        if is_bullet:
            flush_paragraph()
            if not in_list:
                result.append("<ul>")
                in_list = True
            bullet_text = re.sub(r"^[\s]*[•\-\*▸→]\s*|\d+[.)]\s+", "", stripped, count=1)
            result.append(f"<li>{bullet_text}</li>")
        elif is_header:
            flush_list()
            flush_paragraph()
            result.append(f'<p class="desc-heading">{stripped}</p>')
        else:
            flush_list()
            buffer.append(stripped)

    flush_list()
    flush_paragraph()
    return "\n".join(result)


templates.env.filters["beautify_description"] = _beautify_description
app.state.templates = templates

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/jobs/")


from app.routers import actions, applied, autopilot, jobs, manual_fetch, scrape, settings

app.include_router(jobs.router)
app.include_router(applied.router)
app.include_router(scrape.router)
app.include_router(actions.router)
app.include_router(settings.router)
app.include_router(autopilot.router)
app.include_router(manual_fetch.router)
