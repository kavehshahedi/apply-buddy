import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import not_, or_
from sqlmodel import select

from app.config import settings
from app.db import db
from app.models import Job, JobStatus, SearchQuery
from app.services.llm import LLMError, chat_completion
from app.services.utils import load_prompt, load_prompt_model

logger = logging.getLogger("apply-buddy.triage")

# Jobs screened per LLM call. Only a snippet of each description is sent, so a batch stays
# small while replacing ~30 full scoring calls with one.
TRIAGE_BATCH_SIZE = 30
TRIAGE_SNIPPET_CHARS = 400

# Marks a job archived by triage. A job restored to "new" by the user keeps this reason, which
# is how triage knows to leave it to scoring instead of archiving it again.
TRIAGE_REASON_PREFIX = "Triage: "

DEFAULT_TRIAGE_PROMPT = """You are screening job postings for a candidate before a detailed review.
Drop only postings that are clearly irrelevant to the candidate's target roles and background
(an unrelated profession or field, or a seniority far from the candidate's). When in doubt, keep
the posting: a wrongly dropped job is a lost opportunity, a wrongly kept one only costs a review.

Target roles (the candidate's search queries):
{queries}

CV (plain text):
{cv_plain}

Postings (JSON list, descriptions are truncated):
{jobs}

Return JSON: {{"results": [{{"id": <posting id>, "keep": true or false, "reason": "<short reason>"}}]}}
with one entry per posting."""


def _load_triage_prompt() -> str:
    return load_prompt("prompt_triage", DEFAULT_TRIAGE_PROMPT)


def _load_triage_model() -> str | None:
    return load_prompt_model("prompt_triage_model")


def _llm_triage_batch(batch: list[dict], queries: str, cv_plain: str) -> dict[int, str]:
    """Return {job id: reason} for the postings of the batch the LLM drops."""
    prompt = _load_triage_prompt().format(
        queries=queries,
        cv_plain=cv_plain or "(not available)",
        jobs=json.dumps(batch, ensure_ascii=False),
    )
    messages = [
        {"role": "system", "content": "You are a job screening assistant. Return valid JSON only."},
        {"role": "user", "content": prompt},
    ]

    result = chat_completion(messages, response_format="json", model=_load_triage_model())
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```(?:json)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)

    batch_ids = {job["id"] for job in batch}
    dropped = {}
    # Anything short of an explicit keep=false on a known id is kept, so a malformed or
    # partial answer can only cost a scoring call, never a job
    for entry in json.loads(result).get("results", []):
        if not isinstance(entry, dict) or entry.get("keep") is not False:
            continue
        try:
            job_id = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        if job_id in batch_ids:
            dropped[job_id] = str(entry.get("reason") or "Not relevant")
    return dropped


def triage_new_jobs(cv_plain: str, state: dict[str, Any]) -> int:
    """Archive new, unscored jobs the LLM finds clearly irrelevant. Returns the archived count."""
    with db.session() as session:
        jobs = session.exec(
            select(Job).where(
                Job.status == JobStatus.new,
                Job.fit_score.is_(None),
                or_(
                    Job.fit_reason.is_(None),
                    not_(Job.fit_reason.startswith(TRIAGE_REASON_PREFIX)),  # type: ignore
                ),
            )
        ).all()
        if not jobs:
            return 0

        queries = (
            "\n".join(
                f"- {q.keywords}"
                for q in session.exec(select(SearchQuery).where(SearchQuery.enabled)).all()
                if q.keywords
            )
            or "(none)"
        )
        payload = [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description[:TRIAGE_SNIPPET_CHARS],
            }
            for job in jobs
        ]
        batches = [
            payload[i : i + TRIAGE_BATCH_SIZE] for i in range(0, len(payload), TRIAGE_BATCH_SIZE)
        ]

        state["message"] = f"Triaging {len(jobs)} jobs in {len(batches)} batches..."
        dropped: dict[int, str] = {}
        with ThreadPoolExecutor(max_workers=settings.llm_max_concurrency) as executor:
            futures = [
                executor.submit(_llm_triage_batch, batch, queries, cv_plain) for batch in batches
            ]
            for future in as_completed(futures):
                try:
                    dropped.update(future.result())
                except (LLMError, ValueError, AttributeError) as e:
                    # The batch is left untouched: its jobs go on to full scoring
                    logger.error(f"Triage batch failed: {e}")
                    state["errors"] = state.get("errors", 0) + 1

        now = datetime.now(UTC)
        for job in jobs:
            if job.id in dropped:
                job.status = JobStatus.archived
                job.fit_reason = TRIAGE_REASON_PREFIX + dropped[job.id]
                job.updated_at = now
                session.add(job)
        session.commit()

    state["message"] = f"Triage archived {len(dropped)} of {len(jobs)} jobs"
    logger.info(state["message"])
    return len(dropped)
