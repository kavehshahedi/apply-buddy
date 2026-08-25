import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import Job, Setting, JobStatus
from app.services.llm import chat_completion, LLMError, _load_prompt, _load_prompt_model

logger = logging.getLogger("apply-buddy.matcher")


def _load_keywords() -> Dict[str, float]:
    with Session(engine) as session:
        setting = session.get(Setting, "match_keywords")
        if setting and setting.value:
            try:
                return json.loads(setting.value)
            except (json.JSONDecodeError, TypeError):
                pass
    try:
        return json.loads(settings.match_keywords)
    except (json.JSONDecodeError, TypeError):
        return {}


def _load_min_score() -> int:
    with Session(engine) as session:
        setting = session.get(Setting, "min_fit_score")
        if setting and setting.value:
            try:
                return int(setting.value)
            except (ValueError, TypeError):
                pass
    return settings.min_fit_score


def _load_min_keyword_score() -> int:
    with Session(engine) as session:
        setting = session.get(Setting, "min_keyword_score")
        if setting and setting.value:
            try:
                return int(setting.value)
            except (ValueError, TypeError):
                pass
    return settings.min_keyword_score


DEFAULT_SCORE_FIT_PROMPT = """You are a hiring consultant. Score how well this job fits the candidate's CV.

CV (plain text):
{cv_plain}

Job Title: {job_title}
Company: {company}
Description:
{description}

Return JSON with keys:
- fit_score: integer 0-100
- reason: 1-2 sentence explanation
- cv_change_recommended: boolean
- cv_change_reason: string explaining what CV change to make"""


def _load_score_fit_prompt() -> str:
    return _load_prompt("prompt_score_fit", DEFAULT_SCORE_FIT_PROMPT)


def _load_score_fit_model() -> Optional[str]:
    return _load_prompt_model("prompt_score_fit_model")


def _keyword_score(
    title: str, description: str, keywords: Dict[str, float]
) -> Tuple[float, List[str]]:
    if not keywords:
        return 0.0, []
    text = (title + " " + description).lower()
    matched = []
    score = 0.0
    for kw, weight in keywords.items():
        if kw.lower() in text:
            matched.append(kw)
            score += weight
    return score, matched


def _read_cv_text() -> Optional[str]:
    cv_path = settings.cv_tex_path_resolved
    if not cv_path.exists():
        logger.warning(f"CV not found at {cv_path}")
        return None
    try:
        return cv_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read CV: {e}")
        return None


def _strip_tex_to_plain(tex: str) -> str:
    body = tex
    doc_start = body.find(r"\begin{document}")
    doc_end = body.find(r"\end{document}")
    if doc_start != -1 and doc_end != -1:
        body = body[doc_start + len(r"\begin{document}") : doc_end]

    body = re.sub(r"(?<!\\)%.*", "", body)
    body = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", body)
    body = re.sub(r"\[[^\[\]]*\]", "", body)

    body = body.replace(r"\\", " ")
    body = body.replace(r"\~", " ")
    body = body.replace(r"\%", "%")
    body = body.replace(r"\&", "&")
    body = body.replace(r"\_", "_")
    body = body.replace(r"\#", "#")
    body = body.replace(r"\$", "$")
    body = body.replace(r"\{", "{")
    body = body.replace(r"\}", "}")

    body = re.sub(r"\\[a-zA-Z]+", "", body)
    body = body.replace("{", " ").replace("}", " ")
    body = re.sub(r"\s+", " ", body).strip()
    return body


def score_all_new_jobs(
    state: Optional[Dict[str, Any]] = None, force_rescore: bool = False
) -> None:
    if state is None:
        state = {}
    lock = Lock()
    try:
        keywords = _load_keywords()
        min_score = _load_min_score()
        min_kw_score = _load_min_keyword_score()
        cv_text = _read_cv_text()
        cv_plain = _strip_tex_to_plain(cv_text) if cv_text else ""

        with Session(engine) as session:
            query = select(Job).where(Job.status == JobStatus.new)
            if not force_rescore:
                query = query.where(Job.fit_score.is_(None))
            jobs = session.exec(query).all()

            if not jobs:
                state["message"] = "No new jobs to score"
                logger.info("No new jobs to score")
                return

            state["total"] = len(jobs)
            state["current"] = 0

            llm_jobs = []
            for job in jobs:
                kw_score, matched = _keyword_score(job.title, job.description, keywords)
                job.matched_keywords = json.dumps(matched)

                if kw_score < min_kw_score and keywords:
                    job.fit_score = 0
                    job.fit_reason = "Below keyword threshold, skipped LLM scoring"
                    session.add(job)
                    with lock:
                        state["current"] += 1
                        state["message"] = f"Skipped {job.title} (keyword threshold)"
                    continue

                if not cv_plain:
                    job.fit_score = 0
                    job.fit_reason = "CV not available for scoring"
                    session.add(job)
                    with lock:
                        state["current"] += 1
                        state["message"] = f"CV not found for {job.title}"
                    continue

                llm_jobs.append(job)

            if llm_jobs:
                max_conc = settings.llm_max_concurrency
                state["message"] = (
                    f"LLM scoring {len(llm_jobs)} jobs ({max_conc} concurrent)..."
                )
                with ThreadPoolExecutor(max_workers=max_conc) as executor:
                    future_to_job = {
                        executor.submit(_llm_score_job, job, cv_plain): job
                        for job in llm_jobs
                    }
                    for future in as_completed(future_to_job):
                        job = future_to_job[future]
                        try:
                            score_result = future.result()
                            job.fit_score = score_result.get("fit_score", 0)
                            job.fit_reason = score_result.get("reason", "")
                            job.cv_change_recommended = score_result.get(
                                "cv_change_recommended", False
                            )
                            job.cv_change_reason = score_result.get(
                                "cv_change_reason", ""
                            )
                            session.add(job)
                            with lock:
                                state["current"] += 1
                                state["message"] = (
                                    f"Scored {job.title}: {job.fit_score}/100"
                                )
                        except LLMError as e:
                            logger.error(f"LLM scoring failed for job {job.id}: {e}")
                            job.fit_score = 0
                            job.fit_reason = f"LLM scoring error: {e}"
                            session.add(job)
                            with lock:
                                state["current"] += 1
                                state["errors"] += 1
                                state["message"] = f"Error scoring {job.title}: {e}"

            session.commit()
            state["message"] = (
                f"Scored {state['current']} jobs ({state['errors']} errors)"
            )
            logger.info(f"Scored {len(jobs)} jobs")
    except Exception as e:
        logger.exception(f"Scoring crashed: {e}")
        state["errors"] += 1
        state["message"] = f"Scoring error: {e}"
    finally:
        state["running"] = False


def score_single_job(
    job_id: int, state: Optional[Dict[str, Any]] = None
) -> None:
    if state is None:
        state = {}
    try:
        keywords = _load_keywords()
        min_kw_score = _load_min_keyword_score()
        cv_text = _read_cv_text()
        cv_plain = _strip_tex_to_plain(cv_text) if cv_text else ""

        with Session(engine) as session:
            job = session.get(Job, job_id)
            if not job:
                state["message"] = "Job not found"
                return

            kw_score, matched = _keyword_score(job.title, job.description, keywords)
            job.matched_keywords = json.dumps(matched)

            if kw_score < min_kw_score and keywords:
                job.fit_score = 0
                job.fit_reason = "Below keyword threshold, skipped LLM scoring"
                state["message"] = f"Skipped {job.title} (keyword threshold)"
                session.add(job)
                session.commit()
                return

            if not cv_plain:
                job.fit_score = 0
                job.fit_reason = "CV not available for scoring"
                state["message"] = f"CV not found for {job.title}"
                session.add(job)
                session.commit()
                return

            state["message"] = f"LLM scoring {job.title}..."
            score_result = _llm_score_job(job, cv_plain)
            job.fit_score = score_result.get("fit_score", 0)
            job.fit_reason = score_result.get("reason", "")
            job.cv_change_recommended = score_result.get(
                "cv_change_recommended", False
            )
            job.cv_change_reason = score_result.get("cv_change_reason", "")
            session.add(job)
            session.commit()
            state["message"] = f"Scored {job.title}: {job.fit_score}/100"
    except Exception as e:
        logger.exception(f"Scoring single job failed: {e}")
        state["message"] = f"Scoring error: {e}"
    finally:
        state["running"] = False


def _llm_score_job(job: Job, cv_plain: str) -> dict:
    prompt_template = _load_score_fit_prompt()
    prompt = prompt_template.format(
        cv_plain=cv_plain[:8000],
        job_title=job.title,
        company=job.company,
        description=job.description[:4000],
    )

    messages = [
        {
            "role": "system",
            "content": "You are a hiring consultant. Return valid JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    result = chat_completion(messages, response_format="json", model=_load_score_fit_model())
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r"^```(?:json)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
    return json.loads(result)
