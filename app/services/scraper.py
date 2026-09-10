import contextlib
import json
import logging
import os
import re
import threading
import time
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.db import db
from app.models import Job, SearchQuery, Setting

logger = logging.getLogger("apply-buddy.scraper")

# Seconds without progress (session setup or a new job) before a bulk scrape is treated
# as stalled and stopped.
SCRAPE_STALL_TIMEOUT = 90


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


def _inject_linkedin_cookies():
    from app.db import db as _db

    try:
        with _db.session() as _session:
            for key in ("LI_RM_COOKIE", "LI_BCOOKIE"):
                setting = _session.get(Setting, key.lower())
                if setting and setting.value:
                    os.environ[key] = setting.value
    except Exception:
        logger.exception("Failed to inject LinkedIn cookies")


def scrape_single_job(url: str, state: dict[str, Any], db_session: Session | None = None) -> None:
    _inject_linkedin_cookies()
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

    ctx = nullcontext(db_session) if db_session is not None else db.session()
    with ctx as session:
        existing = session.exec(select(Job).where(Job.linkedin_job_id == job_id)).first()

    if existing:
        state["message"] = f"Job already exists: {existing.title} at {existing.company} (skipped)"
        state["current"] = 1
        state["total"] = 1
        state["running"] = False
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

        ctx = nullcontext(db_session) if db_session is not None else db.session()
        with ctx as session:
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


def scrape_jobs(
    queries: list[SearchQuery], state: dict[str, Any], db_session: Session | None = None
) -> None:
    _inject_linkedin_cookies()
    from linkedin_jobs_scraper import LinkedinScraper
    from linkedin_jobs_scraper import linkedin_scraper as scraper_module
    from linkedin_jobs_scraper.events import EventBegin, EventData, Events
    from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters
    from linkedin_jobs_scraper.query import Query, QueryFilters, QueryOptions

    from app.services.scraper_filters import (
        benefits_map,
        commitments_map,
        experience_map,
        industry_map,
        job_function_map,
        relevance_map,
        remote_map,
        salary_map,
        time_filter_map,
        type_filter_map,
    )

    drivers: list = []
    last_activity = [time.monotonic()]
    stop_watchdog = threading.Event()

    original_build_driver = scraper_module.build_driver

    def tracking_build_driver(*args, **kwargs):
        driver = original_build_driver(*args, **kwargs)
        drivers.append(driver)
        return driver

    scraper_module.build_driver = tracking_build_driver

    def watchdog():
        while not stop_watchdog.wait(2):
            if time.monotonic() - last_activity[0] > SCRAPE_STALL_TIMEOUT:
                logger.warning("Scrape stalled, forcing browser shutdown")
                state["message"] = f"Scrape stalled after {state['current']} jobs, stopping"
                for driver in list(drivers):
                    with contextlib.suppress(Exception):
                        driver.quit()
                return

    chrome = _chrome_paths()
    scraper = LinkedinScraper(
        chrome_executable_path=chrome["executable_path"],
        chrome_binary_location=chrome["binary_location"],
        headless=True,
        max_workers=1,
        slow_mo=1.0,
        adaptive_slow_mo=True,
    )

    def on_data(data: EventData):
        last_activity[0] = time.monotonic()
        date_dt = _parse_relative_date(data.date_text)
        if not _is_within_days_back(date_dt):
            state["total"] -= 1
            return

        ctx = nullcontext(db_session) if db_session is not None else db.session()
        with ctx as session:
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

    def on_begin(_data: EventBegin):
        last_activity[0] = time.monotonic()

    def on_error(error):
        logger.error(f"Scrape error: {error}")
        state["errors"] += 1

    def on_end():
        logger.info("Scrape session ended")
        state["message"] = f"Scrape session ended: {state['current']} jobs scraped"
        state["total"] = state["current"]

    scraper.on(Events.BEGIN, on_begin)
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)

    def _parse_json_list(val: str | list | None) -> list:
        if val is None:
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val) if val else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _map_filters(items: list, mapping: dict) -> list:
        return [mapping[i] for i in items if i in mapping]

    linkedin_queries = []
    for q in queries:
        locations = _parse_json_list(q.locations)

        industry = _map_filters(_parse_json_list(q.industry), industry_map)
        job_function = _map_filters(_parse_json_list(q.job_function), job_function_map)
        benefits = _map_filters(_parse_json_list(q.benefits), benefits_map)
        commitments = _map_filters(_parse_json_list(q.commitments), commitments_map)

        filters = QueryFilters(
            company_jobs_url=None,  # type: ignore
            relevance=relevance_map.get(q.relevance, RelevanceFilters.RECENT),
            time=time_filter_map.get(q.time_filter, TimeFilters.ANY),
            type=[type_filter_map.get(q.job_type)] if q.job_type else None,  # type: ignore
            experience=[experience_map.get(q.experience)] if q.experience else None,  # type: ignore
            on_site_or_remote=[remote_map.get(q.on_site_or_remote)]  # type: ignore
            if q.on_site_or_remote  # type: ignore
            else None,  # type: ignore
            industry=industry or None,  # type: ignore
            base_salary=salary_map.get(q.base_salary) if q.base_salary else None,  # type: ignore
            job_function=job_function or None,  # type: ignore
            benefits=benefits or None,  # type: ignore
            commitments=commitments or None,  # type: ignore
            easy_apply=q.easy_apply or False,
            under_10_applicants=q.under_10_applicants or False,
        )

        linkedin_queries.append(
            Query(
                query=q.keywords or "",
                options=QueryOptions(
                    locations=locations or ["United States"],
                    apply_link=False,
                    skip_promoted_jobs=True,
                    page_offset=0,
                    limit=q.limit if q.limit is not None else 25,
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

    state["total"] = sum(q.limit if q.limit is not None else 25 for q in queries)
    state["current"] = 0
    state["message"] = f"Starting scrape with {len(linkedin_queries)} queries..."
    if min_days_back:
        state["message"] += f" (filtering to last {min_days_back} days)"
    state["exact_total_known"] = False

    last_activity[0] = time.monotonic()
    watchdog_thread = threading.Thread(target=watchdog, daemon=True)
    watchdog_thread.start()

    try:
        scraper.run(linkedin_queries)
    except Exception as e:
        logger.exception(f"Scraper crashed: {e}")
        state["errors"] += 1
        state["message"] = f"Scraper error: {e}"
    finally:
        stop_watchdog.set()
        watchdog_thread.join(timeout=5)
        scraper_module.build_driver = original_build_driver
        state["running"] = False
        state["message"] = state.get("message", "Scrape complete")
