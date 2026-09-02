import json
import logging
import re
import time

from sqlmodel import Session

from app.db import engine
from app.models import InterviewSession, Job
from app.services.llm import _load_prompt, _load_prompt_model, chat_completion
from app.services.matcher import _read_cv_text, _strip_tex_to_plain

logger = logging.getLogger("apply-buddy.interview_prep")

DEFAULT_INTERVIEW_QUESTIONS_PROMPT = (
    "You are an interview coach. Based on the job description and the candidate's CV, "
    "generate 10-15 likely interview questions and a skills gap analysis.\n\n"
    "CV: {cv_plain}\n"
    "Job Title: {job_title}\n"
    "Company: {company}\n"
    "Description: {description}\n\n"
    "Return JSON with keys:\n"
    "- questions: array of strings (10-15 interview questions)\n"
    "- skills_gap: array of objects with keys: skill (string), required_level (string), "
    'candidate_level (string), gap_severity ("high"|"medium"|"low"), recommendation (string)'
)

DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT = (
    "You are an interview coach. Evaluate the candidate's answer to the interview question.\n\n"
    "Job Title: {job_title}\n"
    "Company: {company}\n"
    "Job Description: {description}\n"
    "Candidate's CV: {cv_plain}\n"
    "Question: {question}\n"
    "Candidate's Answer: {user_answer}\n\n"
    "Return JSON with keys:\n"
    "- score: integer 0-100\n"
    "- feedback: string (2-3 sentences analyzing the answer)\n"
    "- model_answer: string (what a strong answer would look like)\n"
    "- key_strengths: array of strings\n"
    "- areas_for_improvement: array of strings"
)


def _try_parse_llm_response(raw: str) -> dict | None:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _llm_call_with_retry(
    messages: list[dict[str, str]], model: str | None, max_retries: int = 3
) -> dict:
    last_error = None
    for attempt in range(max_retries):
        try:
            raw = chat_completion(messages, response_format="json", model=model)
            parsed = _try_parse_llm_response(raw)
            if parsed is not None:
                return parsed
            last_error = json.JSONDecodeError("Failed to parse LLM response", raw, 0)
            logger.warning(f"LLM parse error (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt, 10))
        except (KeyError, TypeError, ValueError) as e:
            last_error = e
            logger.warning(f"LLM call error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"LLM response parsing failed after {max_retries} attempts: {last_error}")


def _escape_format(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")


def _load_questions_prompt() -> str:
    return _load_prompt("prompt_interview_questions", DEFAULT_INTERVIEW_QUESTIONS_PROMPT)


def _load_questions_model() -> str | None:
    return _load_prompt_model("prompt_interview_questions_model")


def _load_feedback_prompt() -> str:
    return _load_prompt("prompt_mock_feedback", DEFAULT_MOCK_INTERVIEW_FEEDBACK_PROMPT)


def _load_feedback_model() -> str | None:
    return _load_prompt_model("prompt_mock_feedback_model")


def generate_prep_pack(job_id: int, state: dict):
    try:
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if not job:
                state["message"] = "Job not found"
                state["running"] = False
                return

            cv_text = _read_cv_text()
            cv_plain = _strip_tex_to_plain(cv_text) if cv_text else ""

            prompt_template = _load_questions_prompt()
            prompt = prompt_template.format(
                cv_plain=_escape_format(cv_plain[:8000] if cv_plain else ""),
                job_title=_escape_format(job.title),
                company=_escape_format(job.company),
                description=_escape_format(job.description[:4000]),
            )

            messages = [
                {
                    "role": "system",
                    "content": "You are an interview coach. Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ]

            model = _load_questions_model()
            data = _llm_call_with_retry(messages, model)

            prep_session = _create_prep_session(session, job_id)
            prep_session.prep_questions = json.dumps(data.get("questions", []))
            prep_session.prep_skills_gap = json.dumps(data.get("skills_gap", []))
            session.add(prep_session)
            session.commit()

            state["message"] = "Prep pack generated successfully"
    except Exception as e:
        logger.exception(f"Failed to generate prep pack: {e}")
        state["message"] = f"Error: {e}"
    finally:
        state["running"] = False


def _create_prep_session(session: Session, job_id: int) -> InterviewSession:
    session_obj = InterviewSession(job_id=job_id)
    session.add(session_obj)
    session.commit()
    session.refresh(session_obj)
    return session_obj


def start_session(
    job_id: int, total_questions: int, db_session: Session | None = None
) -> InterviewSession:
    session = db_session or Session(engine)
    own_session = db_session is None
    try:
        from sqlmodel import select

        existing = session.exec(
            select(InterviewSession)
            .where(InterviewSession.job_id == job_id)
            .order_by(InterviewSession.id.desc())
        ).first()

        if not existing or not existing.prep_questions:
            raise ValueError("No prep pack generated yet. Generate a prep pack first.")

        existing_active = session.exec(
            select(InterviewSession).where(
                InterviewSession.job_id == job_id, InterviewSession.status == "in_progress"
            )
        ).first()
        if existing_active:
            existing_active.status = "abandoned"
            session.add(existing_active)
            session.commit()

        questions_list = json.loads(existing.prep_questions)
        selected = questions_list[:total_questions]

        session_obj = InterviewSession(
            job_id=job_id,
            status="in_progress",
            total_questions=min(total_questions, len(selected)),
            current_question=0,
            questions=json.dumps(selected),
            user_answers=json.dumps([]),
            feedback=json.dumps([]),
            overall_summary="",
            prep_questions=existing.prep_questions,
            prep_skills_gap=existing.prep_skills_gap,
        )
        session.add(session_obj)
        session.commit()
        session.refresh(session_obj)
        return session_obj
    finally:
        if own_session:
            session.close()


def submit_answer(session_id: int, answer_text: str, db_session: Session | None = None) -> dict:
    session = db_session or Session(engine)
    own_session = db_session is None
    try:
        session_obj = session.get(InterviewSession, session_id)
        if not session_obj:
            raise ValueError("Session not found")

        questions = json.loads(session_obj.questions)
        answers = json.loads(session_obj.user_answers) if session_obj.user_answers else []
        feedback_list = json.loads(session_obj.feedback) if session_obj.feedback else []

        current_q_idx = session_obj.current_question
        if current_q_idx >= len(questions):
            raise ValueError("All questions have been answered")

        current_question = questions[current_q_idx]
        job = session.get(Job, session_obj.job_id)
        if not job:
            raise ValueError("Job not found")

        cv_text = _read_cv_text()
        cv_plain = _strip_tex_to_plain(cv_text) if cv_text else ""

        prompt_template = _load_feedback_prompt()
        prompt = prompt_template.format(
            job_title=_escape_format(job.title),
            company=_escape_format(job.company),
            description=_escape_format(job.description[:4000]),
            cv_plain=_escape_format(cv_plain[:8000] if cv_plain else ""),
            question=_escape_format(current_question),
            user_answer=_escape_format(answer_text),
        )

        messages = [
            {
                "role": "system",
                "content": "You are an interview coach. Return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ]

        model = _load_feedback_model()
        feedback_data = _llm_call_with_retry(messages, model)

        answers.append(answer_text)
        feedback_list.append(feedback_data)

        next_q_idx = current_q_idx + 1
        if next_q_idx >= len(questions):
            session_obj.status = "completed"
            session_obj.overall_summary = json.dumps(_generate_overall_summary(feedback_list))
        else:
            session_obj.current_question = next_q_idx

        session_obj.user_answers = json.dumps(answers)
        session_obj.feedback = json.dumps(feedback_list)
        session.add(session_obj)
        session.commit()

        next_question = questions[next_q_idx] if next_q_idx < len(questions) else None

        return {
            "feedback": feedback_data,
            "next_question": next_question,
            "session_status": session_obj.status,
        }
    finally:
        if own_session:
            session.close()


def _generate_overall_summary(feedback_list: list) -> dict:
    if not feedback_list:
        return {"overall_score": 0, "summary": "No feedback recorded."}

    scores = [f.get("score", 0) for f in feedback_list if f.get("score") is not None]
    avg_score = sum(scores) // len(scores) if scores else 0
    all_strengths = []
    all_improvements = []
    for f in feedback_list:
        all_strengths.extend(f.get("key_strengths", []))
        all_improvements.extend(f.get("areas_for_improvement", []))

    return {
        "overall_score": avg_score,
        "total_questions": len(feedback_list),
        "key_strengths": all_strengths[:5],
        "areas_for_improvement": all_improvements[:5],
    }
