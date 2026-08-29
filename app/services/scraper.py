import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import Job, SearchQuery

logger = logging.getLogger("apply-buddy.scraper")


def _chrome_paths() -> dict:
    return {
        "executable_path": os.environ.get("CHROMEDRIVER_PATH"),
        "binary_location": os.environ.get("CHROME_BIN"),
    }


_UNIT_MAP = {
    "second": ("seconds", 1),
    "seconds": ("seconds", 1),
    "minute": ("minutes", 1),
    "minutes": ("minutes", 1),
    "hour": ("hours", 1),
    "hours": ("hours", 1),
    "day": ("days", 1),
    "days": ("days", 1),
    "week": ("days", 7),
    "weeks": ("days", 7),
    "month": ("days", 30),
    "months": ("days", 30),
    "year": ("days", 365),
    "years": ("days", 365),
}


def _parse_relative_date(date_text: str) -> datetime | None:
    if not date_text:
        return None
    text = date_text.strip().lower()
    now = datetime.now(UTC)

    m = re.search(
        r"(\d+)\s*\+?\s*(second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s*ago",
        text,
    )
    if m:
        num = int(m.group(1))
        before_unit = text[: m.start(2)].strip()
        if "+" in before_unit:
            num += 1
        unit_info = _UNIT_MAP.get(m.group(2))
        if unit_info:
            kw, multiplier = unit_info
            return now - timedelta(**{kw: num * multiplier})

    if text == "just now":
        return now

    m = re.search(r"\byesterday\b", text)
    if m:
        return now - timedelta(days=1)

    m = re.search(r"\blasts?\s+(week|month|year)\b", text)
    if m:
        unit = m.group(1)
        unit_info = _UNIT_MAP.get(unit)
        if unit_info:
            kw, multiplier = unit_info
            return now - timedelta(**{kw: multiplier})

    return None


def _extract_linkedin_job_id(url: str) -> str | None:
    m = re.search(r"/jobs/view/(\d+)", url)
    if m:
        return m.group(1)
    return None


def scrape_single_job(url: str, state: dict[str, Any]) -> None:
    from linkedin_jobs_scraper import LinkedinScraper
    from linkedin_jobs_scraper.events import EventData, EventNotFound, Events

    job_id = _extract_linkedin_job_id(url)
    if not job_id:
        state["message"] = (
            "Invalid LinkedIn job URL. Expected format: https://www.linkedin.com/jobs/view/1234567890/"
        )
        state["running"] = False
        state["errors"] += 1
        return

    scraped_data = {"data": None, "error": None, "not_found": None}

    def on_data(data: EventData):
        scraped_data["data"] = data  # type: ignore

    def on_error(error):
        scraped_data["error"] = str(error)  # type: ignore

    def on_not_found(data: EventNotFound):
        scraped_data["not_found"] = data.job_id  # type: ignore

    chrome = _chrome_paths()
    scraper = LinkedinScraper(
        chrome_executable_path=chrome["executable_path"],
        chrome_binary_location=chrome["binary_location"],
        headless=True,
        max_workers=1,
        slow_mo=1.0,
        adaptive_slow_mo=True,
        chrome_user_data_dir=str(settings.chrome_profile_path.resolve()),
    )

    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.NOT_FOUND, on_not_found)

    try:
        state["message"] = "Fetching job details from LinkedIn..."
        scraper.scrape_job(url)

        if scraped_data["not_found"]:
            state["message"] = (
                f"Job {scraped_data['not_found']} not found on LinkedIn. It may have been removed or the URL is invalid."
            )
            state["errors"] += 1
            return

        if scraped_data["error"]:
            state["message"] = f"LinkedIn scraping error: {scraped_data['error']}"
            state["errors"] += 1
            return

        data = scraped_data["data"]
        if not data:
            state["message"] = "No job data received from LinkedIn"
            state["errors"] += 1
            return

        state["message"] = f"Processing: {data.title} at {data.company}"

        company_logo = data.company_img_link
        date_dt = _parse_relative_date(data.date_text)

        with Session(engine) as session:
            existing = session.exec(select(Job).where(Job.linkedin_job_id == data.job_id)).first()

            if existing:
                existing.title = data.title or existing.title
                existing.company = data.company or existing.company
                existing.company_logo = company_logo or existing.company_logo
                existing.location = data.place or existing.location
                existing.link = data.link or url
                if data.apply_link:
                    existing.apply_link = data.apply_link
                if data.description:
                    existing.description = data.description
                if data.date_text:
                    existing.date_posted = data.date_text
                    existing.date_posted_dt = date_dt
                existing.updated_at = datetime.now(UTC)
                session.add(existing)
                state["message"] = f"Updated existing job: {data.title} at {data.company}"
            else:
                job = Job(
                    linkedin_job_id=data.job_id,
                    title=data.title or "",
                    company=data.company or "",
                    company_logo=company_logo,
                    location=data.place or "",
                    link=data.link or url,
                    apply_link=data.apply_link,
                    description=data.description or "",
                    date_posted=data.date_text,
                    date_posted_dt=date_dt,
                )
                session.add(job)
                state["message"] = f"Added job: {data.title} at {data.company}"

            session.commit()

        state["current"] = 1
        state["total"] = 1

    except Exception as e:
        logger.exception(f"Unexpected error scraping job {url}")
        state["errors"] += 1
        state["message"] = f"Error: {e}"
    finally:
        state["running"] = False


def scrape_jobs(queries: list[SearchQuery], state: dict[str, Any]) -> None:
    from linkedin_jobs_scraper import LinkedinScraper
    from linkedin_jobs_scraper.events import EventData, Events
    from linkedin_jobs_scraper.filters import (
        ExperienceLevelFilters,
        OnSiteOrRemoteFilters,
        RelevanceFilters,
        TimeFilters,
        TypeFilters,
    )
    from linkedin_jobs_scraper.query import Query, QueryFilters, QueryOptions

    chrome = _chrome_paths()
    scraper = LinkedinScraper(
        chrome_executable_path=chrome["executable_path"],
        chrome_binary_location=chrome["binary_location"],
        headless=True,
        max_workers=1,
        slow_mo=1.0,
        adaptive_slow_mo=True,
        chrome_user_data_dir=str(settings.chrome_profile_path.resolve()),
    )

    def on_data(data: EventData):
        date_dt = _parse_relative_date(data.date_text)
        if not _is_within_days_back(date_dt):
            state["total"] -= 1
            return

        with Session(engine) as session:
            existing = session.exec(select(Job).where(Job.linkedin_job_id == data.job_id)).first()

            if existing:
                existing.title = data.title or existing.title
                existing.company = data.company or existing.company
                existing.company_logo = data.company_img_link or existing.company_logo
                existing.location = data.place or existing.location
                existing.link = data.link or existing.link
                if data.apply_link:
                    existing.apply_link = data.apply_link
                if data.description:
                    existing.description = data.description
                if data.date_text:
                    existing.date_posted = data.date_text
                    existing.date_posted_dt = date_dt
                existing.updated_at = datetime.now(UTC)
                session.add(existing)
            else:
                job = Job(
                    linkedin_job_id=data.job_id,
                    title=data.title or "",
                    company=data.company or "",
                    company_logo=data.company_img_link,
                    location=data.place or "",
                    link=data.link or "",
                    apply_link=data.apply_link,
                    description=data.description or "",
                    date_posted=data.date_text,
                    date_posted_dt=date_dt,
                )
                session.add(job)

            session.commit()

        state["current"] += 1
        state["message"] = f"Scraped job {data.title} at {data.company}"

    def on_error(error):
        logger.error(f"Scrape error: {error}")
        state["errors"] += 1

    def on_end():
        logger.info("Scrape session ended")
        state["message"] = f"Scrape session ended: {state['current']} jobs scraped"
        state["total"] = state["current"]

    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)

    time_filter_map = {
        "day": TimeFilters.DAY,
        "week": TimeFilters.WEEK,
        "month": TimeFilters.MONTH,
        "any": TimeFilters.ANY,
    }
    type_filter_map = {
        "full_time": TypeFilters.FULL_TIME,
        "part_time": TypeFilters.PART_TIME,
        "contract": TypeFilters.CONTRACT,
        "temporary": TypeFilters.TEMPORARY,
        "internship": TypeFilters.INTERNSHIP,
    }
    experience_map = {
        "internship": ExperienceLevelFilters.INTERNSHIP,
        "entry": ExperienceLevelFilters.ENTRY_LEVEL,
        "associate": ExperienceLevelFilters.ASSOCIATE,
        "mid_senior": ExperienceLevelFilters.MID_SENIOR,
        "director": ExperienceLevelFilters.DIRECTOR,
        "executive": ExperienceLevelFilters.EXECUTIVE,
    }
    remote_map = {
        "on_site": OnSiteOrRemoteFilters.ON_SITE,
        "remote": OnSiteOrRemoteFilters.REMOTE,
        "hybrid": OnSiteOrRemoteFilters.HYBRID,
    }

    linkedin_queries = []
    for q in queries:
        locations = []
        try:
            locations = json.loads(q.locations) if isinstance(q.locations, str) else q.locations
        except (json.JSONDecodeError, TypeError):
            locations = []

        filters = QueryFilters(
            company_jobs_url=None,  # type: ignore
            relevance=RelevanceFilters.RECENT,
            time=time_filter_map.get(q.time_filter, TimeFilters.ANY),
            type=[type_filter_map.get(q.job_type)] if q.job_type else None,  # type: ignore
            experience=[experience_map.get(q.experience)] if q.experience else None,  # type: ignore
            on_site_or_remote=[remote_map.get(q.on_site_or_remote)]  # type: ignore
            if q.on_site_or_remote  # type: ignore
            else None,  # type: ignore
        )

        linkedin_queries.append(
            Query(
                query=q.keywords or "",
                options=QueryOptions(
                    locations=locations or ["United States"],
                    apply_link=False,
                    skip_promoted_jobs=True,
                    page_offset=0,
                    limit=q.limit or 25,
                    filters=filters,
                ),
            )
        )

    days_back_values = [q.days_back for q in queries if q.days_back is not None]
    min_days_back = min(days_back_values) if days_back_values else None

    def _is_within_days_back(job_date_dt: datetime | None) -> bool:
        if min_days_back is None:
            return True
        if job_date_dt is None:
            return True
        cutoff = datetime.now(UTC) - timedelta(days=min_days_back)
        return job_date_dt >= cutoff

    state["total"] = sum(q.limit or 25 for q in queries)
    state["current"] = 0
    state["message"] = f"Starting scrape with {len(linkedin_queries)} queries..."
    if min_days_back:
        state["message"] += f" (filtering to last {min_days_back} days)"
    state["exact_total_known"] = False

    try:
        scraper.run(linkedin_queries)
    except Exception as e:
        logger.exception(f"Scraper crashed: {e}")
        state["errors"] += 1
        state["message"] = f"Scraper error: {e}"
    finally:
        state["running"] = False
        state["message"] = state.get("message", "Scrape complete")
